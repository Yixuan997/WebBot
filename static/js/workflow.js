const workflowPageData = window.WORKFLOW_PAGE_DATA || {};
const availableNodes = Array.isArray(workflowPageData.availableNodes) ? workflowPageData.availableNodes : [];
const existingWorkflow = Array.isArray(workflowPageData.existingWorkflow) ? workflowPageData.existingWorkflow : [];
const existingProtocols = Array.isArray(workflowPageData.existingProtocols) ? workflowPageData.existingProtocols : [];
const workflowId = workflowPageData.workflowId ?? null;

let nodeCounter = 1;
const nodes = [];
let debugRecord = null;  // 调试记录
let debugNodeMap = new Map();
let drawflowEditor = null;
let selectedNodeId = null;
let autoLayoutMode = true;
let mobileFitViewTimer = null;
let hasDoneFirstPaint = false;
const EDGE_FIELDS = ['next_node', 'true_branch', 'false_branch', 'loop_body'];
const availableNodeByType = new Map((availableNodes || []).map(n => [n.type, n]));

// 初始化：加载现有节点
window.addEventListener('DOMContentLoaded', () => {
    setCanvasLoading(true);
    let maxNodeNum = 0;
    
    existingWorkflow.forEach(existingNode => {
        const nodeId = existingNode.id || `node_${nodeCounter++}`;
        nodes.push({
            id: nodeId,
            type: existingNode.type,
            config: existingNode.config || {}
        });
        
        // 提取节点ID中的数字，找到最大值
        const match = nodeId.match(/^node_(\d+)$/);
        if (match) {
            const num = parseInt(match[1], 10);
            if (num > maxNodeNum) maxNodeNum = num;
        }
    });
    
    // 计数器从最大节点号+1开始，避免ID重复
    nodeCounter = maxNodeNum + 1;
    
    initDrawflowEditor();
    renderNodes();
});

function setCanvasLoading(visible) {
    const el = document.getElementById('workflowCanvasLoading');
    if (!el) return;
    el.style.display = visible ? 'flex' : 'none';
}

function updateWorkflowStats() {
    const total = nodes.length;
    const business = nodes.filter(n => !['start', 'end'].includes(n.type)).length;
    const totalEl = document.getElementById('totalNodesCount');
    const businessEl = document.getElementById('businessNodesCount');
    if (totalEl) totalEl.textContent = total;
    if (businessEl) businessEl.textContent = business;
}

function getNodeTemplateByType(type) {
    return availableNodeByType.get(type) || null;
}

function closeModalContainer(triggerEl) {
    const modal = triggerEl?.closest('.modal');
    const container = modal?.parentNode;
    if (container) container.remove();
}

function mapEdgeLabel(field) {
    const map = {
        true_branch: '满足',
        false_branch: '不满足'
    };
    return map[field] || '';
}

function firstExistingField(schemaNames, candidates) {
    for (const field of candidates) {
        if (schemaNames.has(field)) return field;
    }
    return '';
}

function getEdgeTextValue(edge) {
    const text = edge?.text;
    if (!text) return '';
    if (typeof text === 'string') return text;
    if (typeof text?.value === 'string') return text.value;
    return '';
}

function nodeSupportsQuickLink(node) {
    const template = getNodeTemplateByType(node.type);
    const schemaNames = new Set((template?.config_schema || []).map(f => f.name));
    return ['next_node', 'loop_body', 'true_branch', 'false_branch']
        .some(field => schemaNames.has(field));
}

function connectSourceToTarget(sourceId, targetId) {
    const sourceNode = nodes.find(n => n.id === sourceId);
    if (!sourceNode || !targetId) return false;
    const template = getNodeTemplateByType(sourceNode.type);
    const schemaNames = new Set((template?.config_schema || []).map(f => f.name));

    if (schemaNames.has('next_node') || sourceNode.type === 'start') {
        sourceNode.config.next_node = targetId;
        return true;
    }
    if (schemaNames.has('loop_body')) {
        sourceNode.config.loop_body = targetId;
        return true;
    }

    const trueField = firstExistingField(schemaNames, ['true_branch']);
    const falseField = firstExistingField(schemaNames, ['false_branch']);
    if (trueField || falseField) {
        const trueValue = trueField ? (sourceNode.config[trueField] || '') : '';
        const falseValue = falseField ? (sourceNode.config[falseField] || '') : '';
        if (trueField && !trueValue) {
            sourceNode.config[trueField] = targetId;
            return true;
        }
        if (falseField && !falseValue) {
            sourceNode.config[falseField] = targetId;
            return true;
        }
        if (trueField) {
            sourceNode.config[trueField] = targetId;
            return true;
        }
        if (falseField) {
            sourceNode.config[falseField] = targetId;
            return true;
        }
    }
    return false;
}

function buildEdges() {
    const exists = new Set(nodes.map(n => n.id));
    const edges = [];
    const explicitBySource = {};

    nodes.forEach(node => {
        EDGE_FIELDS.forEach(field => {
            const targetId = node.config?.[field];
            if (targetId && exists.has(targetId)) {
                if (!explicitBySource[node.id]) explicitBySource[node.id] = new Set();
                explicitBySource[node.id].add(targetId);
                edges.push({
                    sourceId: node.id,
                    targetId,
                    label: mapEdgeLabel(field),
                    field,
                    kind: 'explicit',
                    auto: false
                });
            }
        });
    });

    return edges;
}

function getNodeVisual(node, nodeMeta) {
    const defaults = {
        headColor: '#2f6fec',
        icon: 'N',
        badgeText: '',
        badgeBg: 'rgba(255,255,255,0.2)',
        badgeColor: '#fff'
    };
    const byType = {
        start: { headColor: '#2f6fec', icon: 'S', badgeText: '' },
        end: { headColor: '#111827', icon: 'E', badgeText: '' },
        condition: { headColor: '#f2993a', icon: '?', badgeText: '' },
        loop: { headColor: '#0ea5a4', icon: 'L', badgeText: '' },
        python_snippet: { headColor: '#6d28d9', icon: 'Py', badgeText: '' },
        send_message: { headColor: '#2563eb', icon: 'M', badgeText: '' },
        data: { headColor: '#0f766e', icon: 'D', badgeText: '' }
    };
    return { ...defaults, ...(byType[node.type] || {}) };
}

function getNodeSubtitle(node, nodeMeta) {
    const cfg = node.config || {};
    const short = (v, n = 30) => {
        const s = String(v || '').replace(/\s+/g, ' ').trim();
        if (!s) return '';
        return s.length > n ? `${s.slice(0, n)}...` : s;
    };
    if (node.type === 'condition') {
        const variable = cfg.variable_name || '条件判断';
        const compare = short(cfg.compare_value, 18);
        const op = cfg.condition_type || 'equals';
        return compare ? `${variable} ${op} ${compare}` : variable;
    }
    if (node.type === 'keyword_trigger') {
        const keywords = short(cfg.keywords, 24);
        return keywords ? `关键词: ${keywords}` : '关键词触发';
    }
    if (node.type === 'endpoint') {
        const action = short(cfg.action, 20);
        return action ? `接口: ${action}` : '调用接口';
    }
    if (node.type === 'data_storage') {
        const store = short(cfg.storage_name, 14);
        const op = short(cfg.operation, 10);
        if (store && op) return `${store} / ${op}`;
        if (store) return `存储: ${store}`;
    }
    if (node.type === 'set_variable') {
        const name = short(cfg.variable_name, 18);
        return name ? `变量: ${name}` : '设置变量';
    }
    if (node.type === 'foreach') {
        const listVar = short(cfg.list_variable, 16);
        const itemVar = short(cfg.item_variable, 12);
        if (listVar && itemVar) return `${listVar} -> ${itemVar}`;
        if (listVar) return `遍历: ${listVar}`;
    }
    if (node.type === 'send_message' && cfg.content) {
        return short(cfg.content, 28);
    }
    if (node.type === 'python_snippet' && cfg.snippet_name) {
        return `脚本: ${cfg.snippet_name.replace('.py', '')}`;
    }

    // 通用兜底：提取首个业务字段，避免总是显示已配置跳转
    const ignored = new Set([
        'next_node', 'true_branch', 'false_branch', 'loop_body',
        'allow_continue', 'stop_after_branch', 'mode'
    ]);
    for (const [k, v] of Object.entries(cfg)) {
        if (ignored.has(k)) continue;
        if (v === undefined || v === null || String(v).trim() === '') continue;
        return `${k}: ${short(v, 22)}`;
    }
    return nodeMeta?.description || node.type;
}

function getNodeSelectLabel(node) {
    const nodeMeta = getNodeTemplateByType(node.type);
    const title = nodeMeta?.name || node.type;
    return `${title} (${node.id})`;
}

function escapeNodeHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}



function computeAutoLayoutPositions(allEdges) {
    const levelMap = {};
    const queue = [];
    const nodeSet = new Set(nodes.map(n => n.id));
    const adjacency = {};
    const indegree = {};
    const outdegree = {};
    const nodeTypeById = new Map(nodes.map(n => [n.id, n.type]));

    nodes.forEach(n => {
        adjacency[n.id] = [];
        indegree[n.id] = 0;
        outdegree[n.id] = 0;
    });
    allEdges.forEach(e => {
        if (nodeSet.has(e.sourceId) && nodeSet.has(e.targetId)) {
            adjacency[e.sourceId].push(e.targetId);
            outdegree[e.sourceId] = (outdegree[e.sourceId] || 0) + 1;
            indegree[e.targetId] = (indegree[e.targetId] || 0) + 1;
        }
    });

    const startNodeId = nodes.find(n => n.type === 'start')?.id || nodes[0]?.id;
    if (startNodeId) {
        levelMap[startNodeId] = 0;
        queue.push(startNodeId);
    }

    while (queue.length) {
        const current = queue.shift();
        const currentLevel = levelMap[current] ?? 0;
        (adjacency[current] || []).forEach(targetId => {
            if (levelMap[targetId] === undefined) {
                levelMap[targetId] = currentLevel + 1;
                queue.push(targetId);
            }
        });
    }

    let maxLevel = Math.max(0, ...Object.values(levelMap));
    nodes.forEach(n => {
        if (levelMap[n.id] === undefined) {
            maxLevel += 1;
            levelMap[n.id] = maxLevel;
        }
    });

    // 强制布局语义：start始终第一层，end始终最后一层
    const startIds = nodes.filter(n => n.type === 'start').map(n => n.id);
    const endIds = nodes.filter(n => n.type === 'end').map(n => n.id);
    startIds.forEach(id => {
        levelMap[id] = 0;
    });
    const maxNonEndLevel = Math.max(
        0,
        ...nodes
            .filter(n => n.type !== 'end')
            .map(n => levelMap[n.id] ?? 0)
    );
    endIds.forEach(id => {
        levelMap[id] = maxNonEndLevel + 1;
    });

    const levels = {};
    const parentMap = {};
    nodes.forEach(n => {
        const lv = levelMap[n.id];
        if (!levels[lv]) levels[lv] = [];
        levels[lv].push(n.id);
        parentMap[n.id] = [];
    });
    allEdges.forEach(e => {
        if (parentMap[e.targetId]) parentMap[e.targetId].push(e.sourceId);
    });

    // 关键：按父节点的横向位置重心排序，减少线条交叉和穿卡片感
    const orderedLevels = {};
    const sortedLevelKeys = Object.keys(levels).map(Number).sort((a, b) => a - b);
    const orderIndex = {};

    sortedLevelKeys.forEach(level => {
        const ids = levels[level].slice();
        if (level === 0) {
            ids.sort((a, b) => {
                const aStart = nodeTypeById.get(a) === 'start' ? -1 : 0;
                const bStart = nodeTypeById.get(b) === 'start' ? -1 : 0;
                return aStart - bStart;
            });
        } else {
            ids.sort((a, b) => {
                const parentsA = parentMap[a] || [];
                const parentsB = parentMap[b] || [];
                const centerA = parentsA.length
                    ? parentsA.reduce((sum, p) => sum + (orderIndex[p] ?? 0), 0) / parentsA.length
                    : Number.MAX_SAFE_INTEGER;
                const centerB = parentsB.length
                    ? parentsB.reduce((sum, p) => sum + (orderIndex[p] ?? 0), 0) / parentsB.length
                    : Number.MAX_SAFE_INTEGER;
                if (centerA !== centerB) return centerA - centerB;
                const degreeA = (outdegree[a] || 0) + (indegree[a] || 0);
                const degreeB = (outdegree[b] || 0) + (indegree[b] || 0);
                return degreeB - degreeA;
            });
        }
        orderedLevels[level] = ids;
        ids.forEach((id, idx) => {
            orderIndex[id] = idx;
        });
    });

    const positions = {};
    const maxLevelWidth = Math.max(1, ...Object.values(orderedLevels).map(ids => ids.length));
    const gapX = Math.max(420, Math.min(560, 380 + maxLevelWidth * 18));
    const gapY = 230;
    const centerX = Math.max(760, 560 + (maxLevelWidth * gapX) / 2);
    sortedLevelKeys.forEach(level => {
        const ids = orderedLevels[level] || [];
        const startX = centerX - ((ids.length - 1) * gapX) / 2;
        ids.forEach((id, idx) => {
            positions[id] = {
                x: startX + idx * gapX,
                y: 90 + level * gapY
            };
        });
    });

    // 保持纵向流：开始在上、结束在下，不再强制 start/end 横向偏移
    return positions;
}





function buildDrawflowData() {
    const allEdges = buildEdges();
    const autoPositions = computeAutoLayoutPositions(allEdges);
    const debugByNodeId = debugNodeMap;

    const nodeDrawIdMap = new Map();
    const drawNodes = {};
    let drawIdCounter = 1;

    nodes.forEach((node, index) => {
        const drawId = drawIdCounter++;
        nodeDrawIdMap.set(node.id, drawId);

        const row = Math.floor(index / 4);
        const col = index % 4;
        const nodeMeta = getNodeTemplateByType(node.type);
        const pos = autoLayoutMode ? autoPositions[node.id] : { x: 140 + col * 260, y: 120 + row * 180 };
        const visual = getNodeVisual(node, nodeMeta);
        const dbg = debugByNodeId.get(node.id);
        if (dbg?.status === 'success') {
            visual.badgeText = '运行成功';
            visual.badgeBg = '#d1fae5';
            visual.badgeColor = '#065f46';
        } else if (dbg?.status === 'error') {
            visual.badgeText = '执行失败';
            visual.badgeBg = '#fee2e2';
            visual.badgeColor = '#991b1b';
        }

        let title = nodeMeta?.name || node.type;
        if (node.type === 'start') title = '开始';
        if (node.type === 'end') title = '结束';
        const subtitle = getNodeSubtitle(node, nodeMeta);

        const schemaNames = new Set((nodeMeta?.config_schema || []).map(f => f.name));
        const outputFields = [];
        if (schemaNames.has('true_branch')) outputFields.push('true_branch');
        if (schemaNames.has('false_branch')) outputFields.push('false_branch');
        if (schemaNames.has('next_node') || node.type === 'start') outputFields.push('next_node');
        if (schemaNames.has('loop_body')) outputFields.push('loop_body');
        const outputFieldByClass = {};
        let outputs = {};
        const hasOutgoingEdge = allEdges.some(edge => edge.sourceId === node.id);
        const hasOutputCapability = outputFields.length > 0;
        const isMultiBranchOutput = outputFields.length > 1;

        // 统一单输出锚点：所有节点只保留一个输出球
        // 多分支节点使用 unassigned 回填逻辑（见 syncNodeConfigsFromDrawflow）
        if (hasOutputCapability && hasOutgoingEdge) {
            outputFieldByClass.output_1 = isMultiBranchOutput ? '' : outputFields[0];
            outputs.output_1 = { connections: [] };
        }

        const html = `
            <div class="wf-card-node" data-node-id="${escapeNodeHtml(node.id)}" data-can-quick-link="${nodeSupportsQuickLink(node) ? '1' : '0'}">
                <div class="wf-card-shell">
                    <div class="wf-card-head" style="background:${visual.headColor}">
                        <div class="wf-card-title">
                            <span class="wf-card-icon">${escapeNodeHtml(visual.icon || 'N')}</span>
                            <span>${escapeNodeHtml(title)}</span>
                        </div>
                        <div class="wf-card-actions">
                            <span class="wf-card-id">${escapeNodeHtml(node.id)}</span>
                            ${visual.badgeText ? `<span class="wf-card-badge" style="background:${visual.badgeBg};color:${visual.badgeColor}">${escapeNodeHtml(visual.badgeText)}</span>` : ''}
                        </div>
                    </div>
                    <div class="wf-card-body">${escapeNodeHtml(subtitle || '')}</div>
                </div>
            </div>
        `;

        drawNodes[String(drawId)] = {
            id: drawId,
            name: node.type,
            data: {
                workflow_id: node.id,
                outputFieldByClass
            },
            class: node.type,
            html,
            typenode: false,
            inputs: node.type === 'start' ? {} : { input_1: { connections: [] } },
            outputs,
            pos_x: pos?.x || 140,
            pos_y: pos?.y || 120
        };
    });

    allEdges.forEach(edge => {
        const sourceDrawId = nodeDrawIdMap.get(edge.sourceId);
        const targetDrawId = nodeDrawIdMap.get(edge.targetId);
        if (!sourceDrawId || !targetDrawId) return;
        const sourceNode = drawNodes[String(sourceDrawId)];
        const targetNode = drawNodes[String(targetDrawId)];
        if (!sourceNode || !targetNode) return;
        const outputFieldByClass = sourceNode.data?.outputFieldByClass || {};
        const outputClass = Object.keys(outputFieldByClass).find(k => outputFieldByClass[k] === edge.field) || 'output_1';
        if (!sourceNode.outputs[outputClass]) sourceNode.outputs[outputClass] = { connections: [] };
        if (!targetNode.inputs.input_1) targetNode.inputs.input_1 = { connections: [] };
        sourceNode.outputs[outputClass].connections.push({
            node: String(targetDrawId),
            output: 'input_1'
        });
        targetNode.inputs.input_1.connections.push({
            node: String(sourceDrawId),
            input: outputClass
        });
    });

    return {
        drawflow: {
            Home: {
                data: drawNodes
            }
        }
    };
}

function syncNodeConfigsFromDrawflow() {
    if (!drawflowEditor || typeof drawflowEditor.export !== 'function') return;
    const graph = drawflowEditor.export();
    const sourceMap = {};
    const homeData = graph?.drawflow?.Home?.data || {};

    Object.values(homeData).forEach(drawNode => {
        const sourceId = drawNode?.data?.workflow_id;
        if (!sourceId) return;
        if (!sourceMap[sourceId]) {
            sourceMap[sourceId] = {
                byField: {},
                unassigned: []
            };
        }
        const info = sourceMap[sourceId];
        const outputFieldByClass = drawNode?.data?.outputFieldByClass || {};
        const outputs = drawNode?.outputs || {};

        Object.entries(outputs).forEach(([outputClass, outputObj]) => {
            const field = outputFieldByClass[outputClass] || '';
            (outputObj?.connections || []).forEach(conn => {
                const targetDrawNode = homeData[String(conn.node)];
                const targetId = targetDrawNode?.data?.workflow_id;
                if (!targetId) return;
                if (field && EDGE_FIELDS.includes(field)) {
                    info.byField[field] = targetId;
                } else {
                    info.unassigned.push(targetId);
                }
            });
        });
    });

    nodes.forEach(node => {
        if (!node.config) node.config = {};

        const nodeTemplate = getNodeTemplateByType(node.type);
        const allowed = EDGE_FIELDS.filter(field => (nodeTemplate?.config_schema || []).some(f => f.name === field));
        const mapping = sourceMap[node.id] || { byField: {}, unassigned: [] };

        // 单分支节点：连线与配置一一对应，可安全同步
        if (allowed.length === 1) {
            const field = allowed[0];
            node.config[field] = mapping.byField[field] || mapping.unassigned[0] || '';
            return;
        }

        // 多分支节点：以“编辑节点表单”的字段值为准，不按连线顺序猜测
        // 仅当连线上存在明确字段映射时才覆盖（兼容历史多输出模式）
        allowed.forEach(field => {
            const target = mapping.byField[field];
            if (target) node.config[field] = target;
        });
    });
}

function getNodeLabel(node) {
    const nodeMeta = getNodeTemplateByType(node.type);
    return `${nodeMeta?.name || node.type}(${node.id})`;
}

function validateWorkflowBeforeSave() {
    const errors = [];
    const nodeIdSet = new Set();
    const duplicateIds = new Set();

    nodes.forEach(node => {
        if (!node?.id) return;
        if (nodeIdSet.has(node.id)) duplicateIds.add(node.id);
        nodeIdSet.add(node.id);
    });

    if (duplicateIds.size > 0) {
        errors.push(`存在重复节点ID: ${Array.from(duplicateIds).join(', ')}`);
    }

    if (!nodes.some(n => n.type === 'start')) {
        errors.push('缺少开始节点(start)。');
    }
    if (!nodes.some(n => n.type === 'end')) {
        errors.push('缺少结束节点(end)。');
    }

    nodes.forEach(node => {
        if (!node?.id) {
            errors.push('存在缺少节点ID的节点。');
            return;
        }
        if (!node.config) return;

        const nodeTemplate = getNodeTemplateByType(node.type);
        const allowedFields = EDGE_FIELDS.filter(field => (nodeTemplate?.config_schema || []).some(f => f.name === field));

        allowedFields.forEach(field => {
            const rawValue = node.config[field];
            const targetId = rawValue === undefined || rawValue === null ? '' : String(rawValue).trim();
            if (!targetId) return;

            if (!nodeIdSet.has(targetId)) {
                errors.push(`${getNodeLabel(node)} 的 ${field} 指向不存在节点: ${targetId}`);
                return;
            }
            if (targetId === node.id) {
                errors.push(`${getNodeLabel(node)} 的 ${field} 不能指向自身。`);
            }
        });
    });

    return {
        valid: errors.length === 0,
        errors
    };
}


function getNodeTemplateById(nodeId) {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return null;
    const template = getNodeTemplateByType(node.type);
    return { node, template };
}

function openQuickLinkModal(nodeId) {
    const data = getNodeTemplateById(nodeId);
    if (!data) {
        showToast('未找到节点', 'danger');
        return;
    }
    const { node, template } = data;
    if (!template) {
        showToast('节点模板不存在', 'danger');
        return;
    }

    const schemaNames = new Set((template.config_schema || []).map(f => f.name));
    const hasTrue = schemaNames.has('true_branch');
    const hasFalse = schemaNames.has('false_branch');
    const singleField = ['next_node', 'loop_body'].find(f => schemaNames.has(f));

    if (!hasTrue && !hasFalse && !singleField) {
        showToast('该节点不支持快捷连线，请在编辑中配置。', 'warning');
        return;
    }

    const optionsHtml = nodes
        .filter(n => n.id !== node.id && n.type !== 'start')
        .map(n => {
            return `<option value="${n.id}">${escapeNodeHtml(getNodeSelectLabel(n))}</option>`;
        }).join('');

    const currentTrue = node.config.true_branch || '';
    const currentFalse = node.config.false_branch || '';
    const currentSingle = node.config.next_node || node.config.loop_body || '';

    const bodyHtml = (hasTrue || hasFalse)
        ? `
            ${hasTrue ? `<div class="mb-3"><label class="form-label">满足 -></label><select id="quick_true" class="form-select"><option value="">不跳转（终止流程）</option>${optionsHtml}</select></div>` : ''}
            ${hasFalse ? `<div class="mb-3"><label class="form-label">不满足 -></label><select id="quick_false" class="form-select"><option value="">不跳转（终止流程）</option>${optionsHtml}</select></div>` : ''}
          `
        : `
            <div class="mb-2"><label class="form-label">下一节点</label><select id="quick_single" class="form-select"><option value="">不跳转（终止流程）</option>${optionsHtml}</select></div>
          `;

    const modal = document.createElement('div');
    modal.innerHTML = `
      <div class="modal modal-blur fade show" style="display:block;" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">快捷连接</h5>
              <button type="button" class="btn-close js-modal-close"></button>
            </div>
            <div class="modal-body">${bodyHtml}</div>
            <div class="modal-footer">
              <button type="button" class="btn btn-link link-secondary js-modal-close">取消</button>
              <button
                type="button"
                class="btn btn-primary ms-auto js-quick-apply"
                data-node-id="${escapeNodeHtml(node.id)}"
                data-has-true="${hasTrue ? '1' : '0'}"
                data-has-false="${hasFalse ? '1' : '0'}"
                data-single-field="${escapeNodeHtml(singleField || '')}"
              >搴旂敤</button>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-backdrop fade show"></div>
    `;
    document.body.appendChild(modal);
    modal.querySelectorAll('.js-modal-close').forEach(el => {
        el.addEventListener('click', () => closeModalContainer(el));
    });
    const applyBtn = modal.querySelector('.js-quick-apply');
    if (applyBtn) {
        applyBtn.addEventListener('click', () => {
            applyQuickLink(
                applyBtn.getAttribute('data-node-id') || '',
                applyBtn.getAttribute('data-has-true') === '1',
                applyBtn.getAttribute('data-has-false') === '1',
                applyBtn.getAttribute('data-single-field') || ''
            );
            closeModalContainer(applyBtn);
        });
    }

    const tEl = document.getElementById('quick_true');
    if (tEl && currentTrue) tEl.value = currentTrue;
    const fEl = document.getElementById('quick_false');
    if (fEl && currentFalse) fEl.value = currentFalse;
    const sEl = document.getElementById('quick_single');
    if (sEl && currentSingle) sEl.value = currentSingle;
}

function applyQuickLink(nodeId, hasTrue, hasFalse, singleField) {
    const data = getNodeTemplateById(nodeId);
    if (!data) return;
    const { node, template } = data;
    const schemaNames = new Set((template.config_schema || []).map(f => f.name));
    const trueField = firstExistingField(schemaNames, ['true_branch']);
    const falseField = firstExistingField(schemaNames, ['false_branch']);
    const singleTargetField = singleField || firstExistingField(schemaNames, ['next_node', 'loop_body']);

    if (hasTrue) {
        const v = document.getElementById('quick_true')?.value || '';
        if (trueField) node.config[trueField] = v;
        ['true_branch'].forEach(f => {
            if (f !== trueField && f in node.config) node.config[f] = '';
        });
    }
    if (hasFalse) {
        const v = document.getElementById('quick_false')?.value || '';
        if (falseField) node.config[falseField] = v;
        ['false_branch'].forEach(f => {
            if (f !== falseField && f in node.config) node.config[f] = '';
        });
    }
    if (!hasTrue && !hasFalse && singleTargetField) {
        const v = document.getElementById('quick_single')?.value || '';
        node.config[singleTargetField] = v;
    }

    renderNodes();
    showToast('连接已更新', 'success');
}

function initDrawflowEditor() {
    const container = document.getElementById('drawflowCanvas');
    if (!container || typeof window.Drawflow !== 'function') {
        showToast('Drawflow 加载失败，请检查静态资源。', 'danger');
        setCanvasLoading(false);
        return;
    }

    drawflowEditor = new window.Drawflow(container);
    drawflowEditor.reroute = true;
    drawflowEditor.curvature = 0.3;
    drawflowEditor.line_path = 5;
    drawflowEditor.editor_mode = 'edit';
    drawflowEditor.start();
    if (drawflowEditor.precanvas) {
        drawflowEditor.precanvas.style.transformOrigin = '0 0';
        drawflowEditor.precanvas.style.webkitTransformOrigin = '0 0';
    }

    drawflowEditor.on('nodeSelected', (id) => {
        const drawNode = drawflowEditor?.getNodeFromId ? drawflowEditor.getNodeFromId(id) : null;
        selectedNodeId = drawNode?.data?.workflow_id || null;
        if (selectedNodeId) showNodeDebugPanel(selectedNodeId);
    });

    drawflowEditor.on('nodeUnselected', () => {
        selectedNodeId = null;
        hideNodeDebugPanel();
    });

    drawflowEditor.on('connectionCreated', () => {
        syncNodeConfigsFromDrawflow();
    });

    drawflowEditor.on('connectionRemoved', () => {
        syncNodeConfigsFromDrawflow();
    });

    window.addEventListener('resize', scheduleMobileFitView);
}


function isMobileViewport() {
    return window.matchMedia('(max-width: 991.98px)').matches;
}

function scheduleMobileFitView() {
    if (!isMobileViewport() || !drawflowEditor) return;
    if (mobileFitViewTimer) clearTimeout(mobileFitViewTimer);
    mobileFitViewTimer = setTimeout(() => {
        zoomFit();
    }, 120);
}








function getNodeIndexById(nodeId) {
    return nodes.findIndex(n => n.id === nodeId);
}

function editSelectedNode() {
    if (!selectedNodeId) {
        showToast('请先在流程图中点击一个节点。', 'warning');
        return;
    }
    const idx = getNodeIndexById(selectedNodeId);
    if (idx < 0) {
        showToast('未找到选中节点。', 'danger');
        return;
    }
    editNode(idx);
}

function deleteSelectedNode() {
    if (!selectedNodeId) {
        showToast('请先在流程图中点击一个节点。', 'warning');
        return;
    }
    const idx = getNodeIndexById(selectedNodeId);
    if (idx < 0) {
        showToast('未找到选中节点。', 'danger');
        return;
    }
    deleteNode(idx);
}

function moveSelectedNode(step) {
    if (!selectedNodeId) {
        showToast('请先在流程图中点击一个节点。', 'warning');
        return;
    }
    const idx = getNodeIndexById(selectedNodeId);
    if (idx < 0) {
        showToast('未找到选中节点。', 'danger');
        return;
    }
    const targetIdx = idx + step;
    if (targetIdx < 0 || targetIdx >= nodes.length) {
        showToast('已经到边界位置。', 'warning');
        return;
    }

    const node = nodes[idx];
    const targetNode = nodes[targetIdx];
    if (!node || !targetNode) return;
    if (node.type === 'start' || node.type === 'end' || targetNode.type === 'start' || targetNode.type === 'end') {
        showToast('开始/结束节点位置固定，不能交换。', 'warning');
        return;
    }

    nodes[idx] = targetNode;
    nodes[targetIdx] = node;
    renderNodes();
}

function moveSelectedNodeUp() {
    moveSelectedNode(-1);
}

function moveSelectedNodeDown() {
    moveSelectedNode(1);
}

// 节点分类配置
const categoryConfig = {
    'trigger': { name: '触发器', icon: 'T', color: '#f59f00' },
    'logic': { name: '逻辑控制', icon: 'L', color: '#ae3ec9' },
    'data': { name: '数据处理', icon: 'D', color: '#206bc4' },
    'action': { name: '消息动作', icon: 'A', color: '#2fb344' },
    'other': { name: '其他', icon: 'O', color: '#666' }
};

// 分类映射（合并相似分类）
const categoryMapping = {
    'trigger': 'trigger',
    'logic': 'logic',
    'control': 'logic',      // 流程控制 -> 逻辑控制
    'data': 'data',
    'network': 'data',       // 网络请求 -> 数据处理
    'action': 'action',
    'time': 'other',         // 时间 -> 其他
    'advanced': 'other',     // 高级 -> 其他
    'utility': 'other',      // 工具 -> 其他
    'core': 'other'          // 核心 -> 其他
};

function addNode(sourceNodeId = '') {
    // 过滤掉 start 和 end 节点
    const filteredNodes = availableNodes.filter(node => node.type !== 'start' && node.type !== 'end');
    
    // 按分类分组（使用映射后的分类）
    const nodesByCategory = {};
    filteredNodes.forEach(node => {
        const originalCat = node.category || 'other';
        const cat = categoryMapping[originalCat] || 'other';
        if (!nodesByCategory[cat]) nodesByCategory[cat] = [];
        nodesByCategory[cat].push(node);
    });
    
    // 分类顺序
    const categoryOrder = ['trigger', 'logic', 'data', 'action', 'other'];
    
    // 生成分类列表内容
    const contentHtml = categoryOrder.map(cat => {
        if (!nodesByCategory[cat] || nodesByCategory[cat].length === 0) return '';
        const config = categoryConfig[cat] || { name: cat, icon: 'O', color: '#666' };
        const listHtml = nodesByCategory[cat].map(node => {
            const originalIdx = availableNodes.findIndex(n => n.type === node.type);
            return `<a class="list-group-item list-group-item-action js-select-node-type" href="#" data-node-index="${originalIdx}" data-source-node-id="${escapeNodeHtml(sourceNodeId)}">
                ${node.icon || 'O'} ${node.name}
                <small class="text-muted d-block">${node.description || ''}</small>
            </a>`;
        }).join('');
        return `
            <div class="mb-3">
                <div class="subheader mb-2">${config.icon} ${config.name}</div>
                <div class="list-group list-group-flush">${listHtml}</div>
            </div>`;
    }).join('');
    
    const modal = document.createElement('div');
    modal.innerHTML = `
        <div class="modal modal-blur fade show" style="display: block;" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">閫夋嫨鑺傜偣绫诲瀷</h5>
                        <button type="button" class="btn-close js-modal-close"></button>
                    </div>
                    <div class="modal-body" style="max-height: 500px; overflow-y: auto;">
                        ${contentHtml}
                    </div>
                </div>
            </div>
        </div>
        <div class="modal-backdrop fade show"></div>
    `;
    document.body.appendChild(modal);
    modal.querySelectorAll('.js-modal-close').forEach(el => {
        el.addEventListener('click', () => closeModalContainer(el));
    });
    modal.querySelectorAll('.js-select-node-type').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            const nodeIndex = parseInt(el.getAttribute('data-node-index') || '-1', 10);
            const sourceId = el.getAttribute('data-source-node-id') || '';
            if (nodeIndex >= 0) selectNodeType(nodeIndex, sourceId);
        });
    });
}

// 选中节点类型并创建
function selectNodeType(nodeIndex, sourceNodeId = '') {
    // 关闭弹窗
    const activeModal = document.querySelector('.modal');
    const modalContainer = activeModal?.parentNode;
    if (modalContainer) modalContainer.remove();
    
    // 创建节点
    const nodeTemplate = availableNodes[nodeIndex];
    const nodeId = `node_${nodeCounter++}`;
    const node = {
        id: nodeId,
        type: nodeTemplate.type,
        config: {}
    };
    
    // 初始化默认值
    (nodeTemplate.config_schema || []).forEach(field => {
        node.config[field.name] = field.default !== undefined ? field.default : '';
    });
    
    // 有来源节点时，优先插入到来源节点后面；否则插入到 End 节点前
    if (sourceNodeId) {
        const sourceIndex = nodes.findIndex(n => n.id === sourceNodeId);
        if (sourceIndex >= 0) {
            nodes.splice(sourceIndex + 1, 0, node);
        } else {
            const endNodeIndex = nodes.findIndex(n => n.type === 'end');
            if (endNodeIndex !== -1) {
                nodes.splice(endNodeIndex, 0, node);
            } else {
                nodes.push(node);
            }
        }
    } else {
        const endNodeIndex = nodes.findIndex(n => n.type === 'end');
        if (endNodeIndex !== -1) {
            nodes.splice(endNodeIndex, 0, node);
        } else {
            nodes.push(node);
        }
    }

    let autoLinked = false;
    if (sourceNodeId) {
        autoLinked = connectSourceToTarget(sourceNodeId, nodeId);
    }

    renderNodes();
    if (sourceNodeId) {
        if (autoLinked) {
            showToast('已新增节点并自动连线', 'success');
        } else {
            showToast(`已新增节点（${nodeId}），请手动选择分支连线`, 'warning');
            setTimeout(() => openQuickLinkModal(sourceNodeId), 0);
        }
    } else {
        setTimeout(() => openQuickLinkModal(nodeId), 0);
    }
}

function renderNodes() {
    if (drawflowEditor) {
        const data = buildDrawflowData();
        if (typeof drawflowEditor.clear === 'function') {
            drawflowEditor.clear();
        }
        drawflowEditor.import(data);
        drawflowEditor.editor_mode = 'edit';

        if (!hasDoneFirstPaint) {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    zoomFit();
                    setCanvasLoading(false);
                    hasDoneFirstPaint = true;
                });
            });
        } else if (isMobileViewport()) {
            requestAnimationFrame(() => zoomFit());
        }
    }
    updateWorkflowStats();
    if (selectedNodeId) {
        showNodeDebugPanel(selectedNodeId);
    }
}


function zoomIn() {
    if (drawflowEditor && typeof drawflowEditor.zoom_in === 'function') drawflowEditor.zoom_in();
}


function zoomOut() {
    if (drawflowEditor && typeof drawflowEditor.zoom_out === 'function') drawflowEditor.zoom_out();
}





function zoomFit() {
    if (!drawflowEditor) return;
    const canvas = document.getElementById('drawflowCanvas');
    const precanvas = drawflowEditor.precanvas;
    if (!canvas || !precanvas) return;

    const nodeEls = Array.from(precanvas.querySelectorAll('.drawflow-node'));
    if (!nodeEls.length) return;


    // 先归一化到基准缩放，避免二次 fit 的累计误差
    if (typeof drawflowEditor.zoom_reset === 'function') {
        drawflowEditor.zoom_reset();
    }
    drawflowEditor.canvas_x = 0;
    drawflowEditor.canvas_y = 0;
    precanvas.style.transformOrigin = '0 0';
    precanvas.style.webkitTransformOrigin = '0 0';
    precanvas.style.transform = 'translate(0px, 0px) scale(1)';

    let minLeft = Infinity;
    let minTop = Infinity;
    let maxRight = -Infinity;
    let maxBottom = -Infinity;

    nodeEls.forEach(el => {
        const left = parseFloat(el.style.left || '0');
        const top = parseFloat(el.style.top || '0');
        const width = el.offsetWidth || 292;
        const height = el.offsetHeight || 86;
        minLeft = Math.min(minLeft, left);
        minTop = Math.min(minTop, top);
        maxRight = Math.max(maxRight, left + width);
        maxBottom = Math.max(maxBottom, top + height);
    });

    const padding = isMobileViewport() ? 24 : 48;
    const contentW = Math.max(1, maxRight - minLeft);
    const contentH = Math.max(1, maxBottom - minTop);
    const targetW = Math.max(1, canvas.clientWidth - padding * 2);
    const targetH = Math.max(1, canvas.clientHeight - padding * 2);
    // 放宽缩放下限，避免大流程图无法完整装入视口
    const rawScale = Math.min(targetW / contentW, targetH / contentH);
    const scale = Math.max(0.08, Math.min(2, rawScale));

    // 居中展示（不是贴左上角）
    const tx = ((canvas.clientWidth - contentW * scale) / 2) - minLeft * scale;
    const ty = ((canvas.clientHeight - contentH * scale) / 2) - minTop * scale;

    drawflowEditor.zoom = scale;
    drawflowEditor.canvas_x = tx;
    drawflowEditor.canvas_y = ty;
    if (typeof drawflowEditor.zoom_refresh === 'function') {
        drawflowEditor.zoom_refresh();
    } else {
        precanvas.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    }
}


function getFieldDisplayMeta(field, nodeType) {
    let fieldClass = 'mb-3';
    let dataMode = '';
    let dataShowIf = '';

    if (field.show_if) {
        dataShowIf = `data-show-if='${escapeHtml(JSON.stringify(field.show_if))}'`;
    }

    if (nodeType === 'condition') {
        if (['variable_name', 'condition_type', 'compare_value'].includes(field.name)) {
            dataMode = 'data-condition-mode="simple"';
        } else if (['logic_type', 'conditions'].includes(field.name)) {
            dataMode = 'data-condition-mode="advanced"';
        }
    }

    return { fieldClass, dataMode, dataShowIf };
}

function buildJumpSelectOptions(node, value) {
    return nodes.map(n => {
        if (n.id === node.id || n.type === 'start') return '';
        return `<option value="${escapeNodeHtml(n.id)}" ${value === n.id ? 'selected' : ''}>${escapeNodeHtml(getNodeSelectLabel(n))}</option>`;
    }).join('');
}

function buildVariableSelectOptions(index, value) {
    const variables = [];

    for (let i = 0; i < index; i++) {
        const prevNode = nodes[i];
        const prevTemplate = availableNodes.find(n => n.type === prevNode.type);

        if (prevTemplate && prevTemplate.outputs) {
            prevTemplate.outputs.forEach(out => {
                variables.push({name: out.name, label: `${prevTemplate.name} -> ${out.label}`, source: prevNode.id});
            });
        }

        if (prevNode.config && prevNode.config.save_to) {
            const saveTo = prevNode.config.save_to;
            if (!variables.find(v => v.name === saveTo)) {
                variables.push({name: saveTo, label: `${prevTemplate ? prevTemplate.name : prevNode.type} -> ${saveTo}`, source: prevNode.id});
            }
        }
    }

    return variables.map(v => (
        '<option value="' + escapeNodeHtml(v.name) + '" ' + (value === v.name ? 'selected' : '') + '>' + escapeNodeHtml(v.label) + '</option>'
    )).join('');
}

function buildFieldInputHtml(node, field, value, escapedValue, index) {
    if (field.type === 'select') {
        if (['true_branch', 'false_branch', 'next_node', 'loop_body'].includes(field.name)) {
            const nodeOptions = buildJumpSelectOptions(node, value);
            const defaultLabel = field.name === 'loop_body' ? '请选择循环体节点' : '不跳转（终止流程）';
            return `<select class="form-select" id="field_${field.name}"><option value="">${defaultLabel}</option>${nodeOptions}</select>`;
        }

        if (field.name === 'snippet_name') {
            setTimeout(() => loadSnippets(field.name, value), 100);
            return `<select class="form-select" id="field_${field.name}" onchange="showSnippetMetadata(this.value)"><option value="">加载中...</option></select>
                     <div id="snippet_metadata_info" class="mt-3 p-3 bg-light rounded" style="display: none;">
                         <div class="row g-2">
                             <div class="col-12"><strong>文件:</strong> <span id="snippet_filename">-</span></div>
                             <div class="col-12"><strong>简介:</strong> <span id="snippet_description">-</span></div>
                             <div class="col-6"><strong>作者:</strong> <span id="snippet_author">-</span></div>
                             <div class="col-6"><strong>版本:</strong> <span id="snippet_version">-</span></div>
                         </div>
                     </div>`;
        }

        const options = (field.options || []).map(opt =>
            `<option value="${escapeNodeHtml(opt.value)}" ${value === opt.value ? 'selected' : ''}>${escapeNodeHtml(opt.label)}</option>`
        ).join('');
        let onChange = '';
        if (node.type === 'condition' && field.name === 'mode') {
            onChange = 'onchange="toggleConditionMode(this.value)"';
        } else {
            onChange = `onchange="updateShowIfFields({${field.name}: this.value})"`;
        }
        return `<select class="form-select" id="field_${field.name}" ${onChange}>${options}</select>`;
    }

    if (field.type === 'variable_select') {
        const optionsHtml = buildVariableSelectOptions(index, value);
        const finalOptions = `<option value="">请选择变量...</option>${optionsHtml}`;
        return `<select class="form-select" id="field_${field.name}">${finalOptions}</select>`;
    }

    if (field.type === 'textarea') {
        return `<textarea class="form-control" id="field_${field.name}" rows="3">${escapedValue}</textarea>`;
    }

    if (field.type === 'checkbox') {
        return `
            <label class="form-check form-switch">
                <input class="form-check-input" type="checkbox" id="field_${field.name}" ${value ? 'checked' : ''}>
            </label>`;
    }

    return `<input type="text" class="form-control" id="field_${field.name}" value="${escapedValue}" placeholder="${escapeHtml(field.placeholder || '')}">`;
}

function buildFieldHelpExtraHtml(field) {
    if (!field.help_extra || field.help_extra.length === 0) return '';
    return field.help_extra.map(extra => {
        const badges = extra.values.map(v => `<span class="badge bg-secondary-lt me-1 mb-1">${escapeHtml(v)}</span>`).join('');
        return `<div class="mt-2"><small class="text-muted">${escapeHtml(extra.label)}:</small><div class="mt-1">${badges}</div></div>`;
    }).join('');
}

function buildFieldBlockHtml(node, field, index) {
    const value = node.config[field.name] !== undefined ? node.config[field.name] : (field.default || '');
    const valueText = value === undefined || value === null ? '' : String(value);
    const escapedValue = escapeHtml(valueText);
    const { fieldClass, dataMode, dataShowIf } = getFieldDisplayMeta(field, node.type);
    const inputHtml = buildFieldInputHtml(node, field, value, escapedValue, index);
    const helpExtraHtml = buildFieldHelpExtraHtml(field);

    return `
        <div class="${fieldClass}" ${dataMode} ${dataShowIf}>
            <label class="form-label ${field.required ? 'required' : ''}">${escapeHtml(field.label)}</label>
            ${inputHtml}
            ${field.help ? `<small class="form-hint">${escapeHtml(field.help)}</small>` : ''}
            ${helpExtraHtml}
        </div>
    `;
}

function buildEditNodeModalHtml(nodeTemplateName, fieldsHtml, index) {
    return `
        <div class="modal modal-blur fade show" style="display: block;" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">编辑节点: ${escapeHtml(nodeTemplateName)}</h5>
                        <button type="button" class="btn-close js-modal-close"></button>
                    </div>
                    <div class="modal-body">${fieldsHtml}</div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-link link-secondary js-modal-close">取消</button>
                        <button type="button" class="btn btn-primary ms-auto js-save-node" data-node-index="${index}">保存</button>
                    </div>
                </div>
            </div>
        </div>
        <div class="modal-backdrop fade show"></div>
    `;
}

function editNode(index) {
    const node = nodes[index];
    const nodeTemplate = availableNodes.find(n => n.type === node.type);
    const fieldsHtml = (nodeTemplate.config_schema || []).map(field => buildFieldBlockHtml(node, field, index)).join('');
    const modal = document.createElement('div');
    modal.innerHTML = buildEditNodeModalHtml(nodeTemplate.name, fieldsHtml, index);
    document.body.appendChild(modal);
    modal.querySelectorAll('.js-modal-close').forEach(el => {
        el.addEventListener('click', () => closeModalContainer(el));
    });
    const saveBtn = modal.querySelector('.js-save-node');
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            const idx = parseInt(saveBtn.getAttribute('data-node-index') || '-1', 10);
            if (idx >= 0) saveNode(idx);
            closeModalContainer(saveBtn);
        });
    }
    
    // 如果是条件节点，初始化字段显示状态
    if (node.type === 'condition') {
        setTimeout(() => {
            const currentMode = node.config.mode || 'simple';
            toggleConditionMode(currentMode);
        }, 0);
    }
    
    // 初始化 show_if 条件字段显示
    setTimeout(() => updateShowIfFields(node.config), 0);
}

function saveNode(index) {
    const node = nodes[index];
    const nodeTemplate = availableNodes.find(n => n.type === node.type);
    
    // 先收集所有字段的当前值
    const currentValues = {};
    (nodeTemplate.config_schema || []).forEach(field => {
        const element = document.getElementById(`field_${field.name}`);
        if (!element) return;
        if (field.type === 'checkbox') {
            currentValues[field.name] = element.checked;
        } else {
            currentValues[field.name] = element.value;
        }
    });
    
    // 保存字段，并清理隐藏字段的值
    (nodeTemplate.config_schema || []).forEach(field => {
        const element = document.getElementById(`field_${field.name}`);
        if (!element) return;
        
        // 检查字段是否应该显示（根据 show_if 条件）
        let shouldSave = true;
        if (field.show_if) {
            for (const [key, expectedValue] of Object.entries(field.show_if)) {
                if (currentValues[key] !== expectedValue) {
                    shouldSave = false;
                    break;
                }
            }
        }
        
        if (shouldSave) {
            // 保存当前值
            node.config[field.name] = currentValues[field.name];
        } else {
            // 清理隐藏字段的值（设为默认值或空）
            node.config[field.name] = field.default !== undefined ? field.default : '';
        }
    });
    
    renderNodes();
}

function deleteNode(index) {
    if (confirm('确定要删除这个节点吗？')) {
        const removedNode = nodes[index];
        if (!removedNode) return;
        if (['start', 'end'].includes(removedNode.type)) {
            showToast('开始/结束节点不允许删除。', 'warning');
            return;
        }
        nodes.forEach(n => {
            EDGE_FIELDS.forEach(field => {
                if (n.config && n.config[field] === removedNode.id) {
                    n.config[field] = '';
                }
            });
        });
        nodes.splice(index, 1);
        if (selectedNodeId === removedNode.id) {
            selectedNodeId = null;
            hideNodeDebugPanel();
        }
        renderNodes();
    }
}

// 通用：根据 show_if 条件更新字段显示
function updateShowIfFields(currentValues) {
    // 获取当前所有字段的值
    const allValues = {...currentValues};
    document.querySelectorAll('[id^="field_"]').forEach(el => {
        const fieldName = el.id.replace('field_', '');
        if (!(fieldName in allValues)) {
            allValues[fieldName] = el.type === 'checkbox' ? el.checked : el.value;
        }
    });
    
    // 遍历所有带 data-show-if 的字段
    document.querySelectorAll('[data-show-if]').forEach(el => {
        try {
            const condition = JSON.parse(el.getAttribute('data-show-if'));
            let shouldShow = true;
            
            // 检查所有条件
            for (const [key, expectedValue] of Object.entries(condition)) {
                if (allValues[key] !== expectedValue) {
                    shouldShow = false;
                    break;
                }
            }
            
            el.style.display = shouldShow ? 'block' : 'none';
        } catch (e) {
            console.error('show_if parse error:', e);
        }
    });
}

// 条件节点：根据模式切换字段显示
function toggleConditionMode(mode) {
    // 查找所有带有 data-condition-mode 属性的字段
    const simpleFields = document.querySelectorAll('[data-condition-mode="simple"]');
    const advancedFields = document.querySelectorAll('[data-condition-mode="advanced"]');
    
    if (mode === 'simple') {
        // 显示简单模式字段，隐藏高级模式字段
        simpleFields.forEach(el => el.style.display = 'block');
        advancedFields.forEach(el => el.style.display = 'none');
    } else if (mode === 'advanced') {
        // 隐藏简单模式字段，显示高级模式字段
        simpleFields.forEach(el => el.style.display = 'none');
        advancedFields.forEach(el => el.style.display = 'block');
    }
}

// 全局变量：存储代码片段数据
let snippetsData = [];

// 辅助函数：加载代码片段列表
function loadSnippets(fieldName, currentValue) {
    fetch('/admin/workflows/snippets')
        .then(res => res.json())
        .then(data => {
            const selectEl = document.getElementById(`field_${fieldName}`);
            if (selectEl && data.success) {
                snippetsData = data.snippets;
                const options = data.snippets.map(s => 
                    `<option value="${s.filename}" ${currentValue === s.filename ? 'selected' : ''}>${s.name}</option>`
                ).join('');
                selectEl.innerHTML = `<option value="">请选择代码片段</option>${options}`;
                
                // 如果有当前值，显示元数据
                if (currentValue) {
                    showSnippetMetadata(currentValue);
                }
            }
        })
        .catch(console.error);
}

// 显示代码片段元数据
function showSnippetMetadata(filename) {
    const metadataDiv = document.getElementById('snippet_metadata_info');
    if (!metadataDiv) return;
    
    if (!filename) {
        metadataDiv.style.display = 'none';
        return;
    }
    
    const snippet = snippetsData.find(s => s.filename === filename);
    if (snippet) {
        document.getElementById('snippet_filename').textContent = snippet.filename;
        document.getElementById('snippet_description').textContent = snippet.description || '无';
        document.getElementById('snippet_author').textContent = snippet.author || '未知';
        document.getElementById('snippet_version').textContent = snippet.version || '1.0.0';
        metadataDiv.style.display = 'block';
    } else {
        metadataDiv.style.display = 'none';
    }
}

// 加载调试记录
function loadDebugRecord() {
    fetch(`/admin/workflows/${workflowId}/debug`)
        .then(res => res.json())
        .then(data => {
            if (data.success && data.record) {
                debugRecord = data.record;
                debugNodeMap = new Map((debugRecord.nodes || []).map(n => [n.id, n]));
                renderNodes();  // 重新渲染节点以显示调试信息
                showDebugSummary();
                if (selectedNodeId) showNodeDebugPanel(selectedNodeId);
                showToast('已加载调试记录', 'success');
            } else {
                debugRecord = null;
                debugNodeMap = new Map();
                hideNodeDebugPanel();
                showToast(data.message || '暂无调试记录', 'warning');
            }
        })
        .catch(err => {
            console.error('加载调试记录失败:', err);
            showToast('加载调试记录失败', 'danger');
        });
}

// 清除调试记录
function clearDebugRecord() {
    if (!confirm('确定要清除调试记录吗？')) return;
    
    fetch(`/admin/workflows/${workflowId}/debug/clear`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                debugRecord = null;
                debugNodeMap = new Map();
                renderNodes();
                hideDebugSummary();
                hideNodeDebugPanel();
                showToast('调试记录已清除', 'success');
            } else {
                showToast(data.message || '清除失败', 'danger');
            }
        })
        .catch(err => {
            console.error('清除调试记录失败:', err);
            showToast('清除调试记录失败', 'danger');
        });
}

// 获取节点的调试信息
function getNodeDebugInfo(nodeId) {
    if (!debugRecord || !nodeId) return null;
    return debugNodeMap.get(nodeId) || null;
}

// 格式化调试数据
function formatDebugData(data) {
    if (data === null || data === undefined) return '';
    if (typeof data === 'string') {
        try {
            return JSON.stringify(JSON.parse(data), null, 2);
        } catch {
            return data;
        }
    }
    return JSON.stringify(data, null, 2);
}

// 显示调试摘要
function showDebugSummary() {
    if (!debugRecord) return;
    
    // 移除旧的摘要
    hideDebugSummary();
    
    const statusBadge = debugRecord.status === 'success' 
        ? '<span class="badge bg-success-lt text-success">成功</span>' 
        : '<span class="badge bg-danger-lt text-danger">失败</span>';
    const triggerMsg = debugRecord.trigger_message || '-';
    const nodeCount = debugRecord.nodes ? debugRecord.nodes.length : 0;
    const successCount = debugRecord.nodes ? debugRecord.nodes.filter(n => n.status === 'success').length : 0;
    
    const summaryHtml = `
        <div id="debugSummary" class="card card-sm mb-3">
            <div class="card-body py-2">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="fw-bold">调试记录</span>
                    <div>
                        ${statusBadge}
                        <a href="#" class="text-muted ms-2" onclick="clearDebugRecord(); return false;" title="清除">×</a>
                    </div>
                </div>
                <div class="text-muted" style="font-size:12px;">
                    <span class="me-3">时间: ${debugRecord.trigger_time || '-'}</span>
                    <span class="me-3">用户: ${debugRecord.user_id || '-'}</span>
                    <span class="me-3">群: ${debugRecord.group_id || '-'}</span>
                    <span>节点: ${successCount}/${nodeCount}</span>
                </div>
                <details class="mt-2" style="font-size:12px;">
                    <summary style="cursor:pointer; color:#206bc4;">触发消息</summary>
                    <pre class="bg-dark text-white p-2 mt-1 rounded" style="font-size:12px; max-height:100px; overflow:auto; white-space:pre-wrap; word-break:break-all;">${escapeHtml(triggerMsg)}</pre>
                </details>
            </div>
        </div>
    `;
    
    const canvasWrap = document.querySelector('.workflow-canvas');
    if (canvasWrap) {
        canvasWrap.insertAdjacentHTML('beforebegin', summaryHtml);
    }
}

function hideNodeDebugPanel() {
    const panel = document.getElementById('nodeDebugPanel');
    const body = document.getElementById('nodeDebugPanelBody');
    if (body) body.innerHTML = '';
    if (panel) panel.style.display = 'none';
}

function showNodeDebugPanel(nodeId) {
    const panel = document.getElementById('nodeDebugPanel');
    const body = document.getElementById('nodeDebugPanelBody');
    if (!panel || !body || !nodeId) return;

    const node = nodes.find(n => n.id === nodeId);
    const nodeMeta = availableNodes.find(n => n.type === node?.type);
    const debugInfo = getNodeDebugInfo(nodeId);

    if (!debugRecord) {
        body.innerHTML = `<div class="text-muted">请先点击“调试”加载最近一次执行记录。</div>`;
        panel.style.display = 'block';
        return;
    }
    if (!debugInfo) {
        body.innerHTML = `
            <div class="meta">${escapeHtml(nodeMeta?.name || node?.type || nodeId)} (${escapeHtml(nodeId)})</div>
            <div class="text-muted">当前调试记录中没有该节点执行数据。</div>
        `;
        panel.style.display = 'block';
        return;
    }

    const statusBadge = debugInfo.status === 'success'
        ? '<span class="badge bg-success-lt text-success">成功</span>'
        : '<span class="badge bg-danger-lt text-danger">失败</span>';
    const duration = debugInfo.duration_ms !== undefined ? `${debugInfo.duration_ms}ms` : '-';
    const outputText = formatDebugData(debugInfo.output);
    const inputText = formatDebugData(debugInfo.input);
    const errorText = debugInfo.error ? escapeHtml(debugInfo.error) : '';

    body.innerHTML = `
        <div class="meta">${escapeHtml(nodeMeta?.name || node?.type || nodeId)} (${escapeHtml(nodeId)})</div>
        <div class="mb-2">${statusBadge} <span class="text-muted ms-2">耗时: ${duration}</span></div>
        ${errorText ? `<div class="mb-2 text-danger"><strong>错误:</strong> ${errorText}</div>` : ''}
        ${inputText ? `<div class="mb-2"><div class="mb-1 fw-semibold">输入</div><pre>${escapeHtml(inputText)}</pre></div>` : ''}
        ${outputText ? `<div><div class="mb-1 fw-semibold">输出</div><pre>${escapeHtml(outputText)}</pre></div>` : ''}
    `;
    panel.style.display = 'block';
}

// 隐藏调试摘要
function hideDebugSummary() {
    const el = document.getElementById('debugSummary');
    if (el) el.remove();
}

// HTML 转义
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ========== 表单提交 ==========

function submitWorkflow(event) {
    event.preventDefault();
    syncNodeConfigsFromDrawflow();
    
    // 节点不能为空
    if (nodes.length === 0) {
        alert('工作流节点不能为空');
        return;
    }

    const validation = validateWorkflowBeforeSave();
    if (!validation.valid) {
        alert(`保存失败，请先修正以下问题：\n\n- ${validation.errors.join('\n- ')}`);
        return;
    }
    
    // 构建工作流节点配置
    const workflowConfig = {
        workflow: nodes
    };
    
    // 通过表单提交
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = window.location.pathname;
    
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'workflow_data';
    input.value = JSON.stringify(workflowConfig);
    form.appendChild(input);
    
    document.body.appendChild(form);
    form.submit();
}
