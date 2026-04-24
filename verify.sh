#!/bin/bash
# =============================================================================
# 模块详细设计验证脚本（完整版）
# 基于 SKILL.md、SKILL-STANDARDS.md、THREE-PASS-VALIDATION.md 标准
# 参考文档：M04 合约管理、M05 交付订单、M06 数据使用控制
# =============================================================================

MODULE="$1"
DOC="$2"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# 参数检查
if [ -z "$MODULE" ] || [ -z "$DOC" ]; then
    echo -e "${RED}❌ 错误：请提供模块编号和文档路径${NC}"
    echo "使用方式：bash verify.sh <模块编号> <文档路径>"
    exit 1
fi

if [ ! -f "$DOC" ]; then
    echo -e "${RED}❌ 文档不存在：$DOC${NC}"
    exit 1
fi

echo "=================================================="
echo -e "  ${BOLD}模块详细设计验证${NC}"
echo "  模块：$MODULE"
echo "  文档：$DOC"
echo "=================================================="
echo ""

# 计数器
PASS=0
FAIL=0
WARN=0

# 安全计数函数
count_pattern() {
    local result
    result=$(grep -c "$1" "$2" 2>/dev/null) || result=0
    result=${result:-0}
    result=$(echo "$result" | tr -d '[:space:]')
    if ! [[ "$result" =~ ^[0-9]+$ ]]; then
        result=0
    fi
    echo "$result"
}

# =============================================================================
# 第一部分：SKILL-STANDARDS.md - 业务流程设计标准
# =============================================================================
echo -e "${BLUE}${BOLD}【第一部分：业务流程设计标准】${NC}"
echo "=================================================="

# 1.1 流程图数量检查（一个模块应该有多个关键流程）
echo -e "\n${YELLOW}1. 流程图检查${NC}"
FLOW_COUNT=$(grep -c "#### 流程 [0-9]*：\|流程 [0-9]*[.]\|流程 1：\|流程 2：\|流程 3：" "$DOC" 2>/dev/null || echo "0")
# 如果找不到带编号的流程，尝试找泳道图
if [ "$FLOW_COUNT" -eq 0 ]; then
    FLOW_COUNT=$(grep -c "graph TD\|graph LR\|sequenceDiagram\|┌─\|│" "$DOC" 2>/dev/null || echo "0")
fi

if [ "$FLOW_COUNT" -ge 2 ]; then
    echo -e "${GREEN}✅ 流程图数量：$FLOW_COUNT 个 (要求≥2)${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 流程图数量：$FLOW_COUNT 个 (要求≥2，一个模块应该有多个关键流程)${NC}"
    FAIL=$((FAIL+1))
fi

# 1.2 流程图深度检查（总步骤数）
TOTAL_FLOW_STEPS=$(grep -E "^[[:space:]]*[0-9]+[.]" "$DOC" 2>/dev/null | wc -l)
TOTAL_FLOW_STEPS=$(echo "$TOTAL_FLOW_STEPS" | tr -d '[:space:]')

if [ "$TOTAL_FLOW_STEPS" -ge 30 ]; then
    echo -e "${GREEN}✅ 流程图总步骤：$TOTAL_FLOW_STEPS 步 (要求≥30)${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 流程图总步骤：$TOTAL_FLOW_STEPS 步 (要求≥30)${NC}"
    FAIL=$((FAIL+1))
fi

# 1.3 流程说明（每个流程都应该有详细说明）
if grep -q "流程说明" "$DOC"; then
    FLOW_EXPLAIN_COUNT=$(grep -c "流程说明" "$DOC" 2>/dev/null || echo "0")
    if [ "$FLOW_EXPLAIN_COUNT" -ge "$FLOW_COUNT" ]; then
        echo -e "${GREEN}✅ 流程说明：$FLOW_EXPLAIN_COUNT 个 (覆盖所有流程)${NC}"
        PASS=$((PASS+1))
    else
        echo -e "${YELLOW}⚠️  流程说明：$FLOW_EXPLAIN_COUNT 个 (建议覆盖所有$FLOW_COUNT 个流程)${NC}"
        WARN=$((WARN+1))
    fi
else
    echo -e "${RED}❌ 流程说明：缺失${NC}"
    FAIL=$((FAIL+1))
fi

# 1.4 字段流转表
if grep -q "字段流转表\|字段流转" "$DOC"; then
    echo -e "${GREEN}✅ 字段流转表：已包含${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 字段流转表：缺失${NC}"
    FAIL=$((FAIL+1))
fi

# 1.5 状态机/状态流转图
if grep -q "状态机\|stateDiagram\|状态流转\|状态图" "$DOC"; then
    echo -e "${GREEN}✅ 状态机图：已包含${NC}"
    PASS=$((PASS+1))
else
    echo -e "${YELLOW}⚠️  状态机图：建议补充 (如状态≥3 个)${NC}"
    WARN=$((WARN+1))
fi

# 1.6 分支场景处理（如果...则...否则...）
if grep -q "如果.*则\|如果.*就\|分支\|否则\|if.*else" "$DOC"; then
    BRANCH_COUNT=$(grep -c "如果.*则\|如果.*就\|否则" "$DOC" 2>/dev/null || echo "0")
    echo -e "${GREEN}✅ 分支场景处理：$BRANCH_COUNT 处${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 分支场景处理：缺失${NC}"
    FAIL=$((FAIL+1))
fi

# 1.7 关键节点标注（如判断/决策点）
if grep -q "┌──────┬──────┐\|┌───────┐\|决策\|判断\|?" "$DOC"; then
    echo -e "${GREEN}✅ 关键节点标注：已包含${NC}"
    PASS=$((PASS+1))
else
    echo -e "${YELLOW}⚠️  关键节点标注：建议补充（判断/决策点）${NC}"
    WARN=$((WARN+1))
fi

# =============================================================================
# 第二部分：SKILL-STANDARDS.md - 核心逻辑设计标准
# =============================================================================
echo -e "\n${BLUE}${BOLD}【第二部分：核心逻辑设计标准】${NC}"
echo "=================================================="

# 2.1 核心逻辑识别（从需求识别 + 从流程识别）
if grep -q "核心逻辑识别\|从需求识别\|从流程识别" "$DOC"; then
    echo -e "${GREEN}✅ 核心逻辑识别：已包含${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 核心逻辑识别：缺失${NC}"
    FAIL=$((FAIL+1))
fi

# 2.2 代码示例数量（参考文档标准：M04=5 个，M05=18 个，M06=11 个）
CODE_BLOCKS=$(count_pattern '\`\`\`java\|\`\`\`python' "$DOC")
if [ "$CODE_BLOCKS" -ge 5 ]; then
    echo -e "${GREEN}✅ 代码示例：$CODE_BLOCKS 个 (要求≥5)${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 代码示例：$CODE_BLOCKS 个 (要求≥5)${NC}"
    FAIL=$((FAIL+1))
fi

# 2.3 伪代码/流程描述（复杂接口需要伪代码）
if grep -q "// .*()\|public.*(\|private.*(\|protected.*(" "$DOC"; then
    PSEUDO_CODE=$(grep -c "// .*()\|public.*(\|private.*(" "$DOC" 2>/dev/null || echo "0")
    echo -e "${GREEN}✅ 伪代码/方法定义：$PSEUDO_CODE 个${NC}"
    PASS=$((PASS+1))
else
    echo -e "${YELLOW}⚠️  伪代码/方法定义：建议补充（复杂接口需要）${NC}"
    WARN=$((WARN+1))
fi

# 2.4 业务规则实现位置
if grep -q "业务规则实现位置\|业务规则.*实现" "$DOC"; then
    echo -e "${GREEN}✅ 业务规则实现位置：已包含${NC}"
    PASS=$((PASS+1))
else
    echo -e "${YELLOW}⚠️  业务规则实现位置：建议补充${NC}"
    WARN=$((WARN+1))
fi

# 2.5 公共组件/公共方法设计
if grep -q "公共组件\|公共方法\|Utils\|Helper\|Service\|Manager" "$DOC"; then
    echo -e "${GREEN}✅ 公共组件/方法设计：已包含${NC}"
    PASS=$((PASS+1))
else
    echo -e "${YELLOW}⚠️  公共组件/方法设计：建议补充${NC}"
    WARN=$((WARN+1))
fi

# =============================================================================
# 第三部分：SKILL-STANDARDS.md - 接口设计标准
# =============================================================================
echo -e "\n${BLUE}${BOLD}【第三部分：接口设计标准】${NC}"
echo "=================================================="

# 3.1 接口展开数量
INTERFACES=$(count_pattern "### $MODULE-API-" "$DOC")
echo -e "📊 接口展开数量：$INTERFACES 个"
if [ "$INTERFACES" -ge 10 ]; then
    echo -e "${GREEN}✅ 接口展开：符合要求${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 接口展开：不足 (要求≥10)${NC}"
    FAIL=$((FAIL+1))
fi

# 3.2 接口 9 要素检查
BASIC_INFO=$(count_pattern "接口基本信息" "$DOC")
REQUEST_PARAM=$(count_pattern "请求参数" "$DOC")
RESPONSE_PARAM=$(count_pattern "响应参数" "$DOC")
BUSINESS_LOGIC=$(count_pattern "业务逻辑" "$DOC")
ERROR_CODE=$(count_pattern "错误码" "$DOC")

echo -e "  - 接口基本信息表：$BASIC_INFO 个"
echo -e "  - 请求参数表：$REQUEST_PARAM 个"
echo -e "  - 响应参数表：$RESPONSE_PARAM 个"
echo -e "  - 业务逻辑：$BUSINESS_LOGIC 个"
echo -e "  - 错误码表：$ERROR_CODE 个"

if [ "$BASIC_INFO" -ge "$INTERFACES" ] && \
   [ "$REQUEST_PARAM" -ge "$INTERFACES" ] && \
   [ "$RESPONSE_PARAM" -ge "$INTERFACES" ]; then
    echo -e "${GREEN}✅ 接口 9 要素：完整${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 接口 9 要素：不完整${NC}"
    FAIL=$((FAIL+1))
fi

# 3.3 业务逻辑深度检查（区分简单/复杂接口）
echo -e "\n${YELLOW}业务逻辑深度检查${NC}"
# 统计每个接口的业务逻辑步骤数
COMPLEX_INTERFACES=0
SIMPLE_INTERFACES=0

for i in $(seq 1 20); do
    API_SECTION=$(grep -A200 "### $MODULE-API-$(printf '%02d' $i)" "$DOC" 2>/dev/null | head -200)
    if [ -n "$API_SECTION" ]; then
        # 检查接口复杂度（基于关键词）
        COMPLEXITY=0
        echo "$API_SECTION" | grep -q "推送\|同步\|签名\|加密\|双向" && COMPLEXITY=$((COMPLEXITY+3))
        echo "$API_SECTION" | grep -q "状态.*=\|status.*=" && COMPLEXITY=$((COMPLEXITY+1))
        echo "$API_SECTION" | grep -q "如果.*则\|否则" && COMPLEXITY=$((COMPLEXITY+1))
        
        API_STEPS=$(echo "$API_SECTION" | grep -A100 "业务逻辑" | grep -c "^[0-9]\+\." 2>/dev/null || echo "0")
        
        if [ "$COMPLEXITY" -ge 3 ]; then
            # 复杂接口要求≥15 步
            if [ "$API_STEPS" -ge 15 ]; then
                COMPLEX_INTERFACES=$((COMPLEX_INTERFACES+1))
            else
                echo -e "${YELLOW}⚠️  接口$MODULE-API-$(printf '%02d' $i)：复杂接口但业务逻辑仅$API_STEPS 步 (要求≥15)${NC}"
            fi
        else
            # 简单接口要求≥5 步
            if [ "$API_STEPS" -ge 5 ]; then
                SIMPLE_INTERFACES=$((SIMPLE_INTERFACES+1))
            fi
        fi
    fi
done

echo -e "  复杂接口 (≥15 步): $COMPLEX_INTERFACES 个"
echo -e "  简单接口 (≥5 步): $SIMPLE_INTERFACES 个"

if [ "$COMPLEX_INTERFACES" -ge 1 ] || [ "$SIMPLE_INTERFACES" -ge 5 ]; then
    echo -e "${GREEN}✅ 业务逻辑深度：符合要求${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 业务逻辑深度：不足${NC}"
    FAIL=$((FAIL+1))
fi

# 3.4 错误码数量 (复杂接口要求≥8 个)
if [ "$ERROR_CODE" -ge 8 ]; then
    echo -e "${GREEN}✅ 错误码数量：$ERROR_CODE 个 (要求≥8)${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 错误码数量：$ERROR_CODE 个 (要求≥8)${NC}"
    FAIL=$((FAIL+1))
fi

# 3.5 禁止表述检查
echo -e "\n${YELLOW}禁止表述检查${NC}"
FORBIDDEN_COUNT=0
for pattern in "其他接口类似" "其余接口见上" "同上)" "篇幅限制" "此处省略" "按照相同模板"; do
    if grep -q "$pattern" "$DOC"; then
        echo -e "${RED}❌ 发现禁止表述：'$pattern'${NC}"
        grep -n "$pattern" "$DOC" | head -1
        FORBIDDEN_COUNT=$((FORBIDDEN_COUNT+1))
    fi
done

if [ "$FORBIDDEN_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ 无省略表述${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 发现$FORBIDDEN_COUNT 处省略表述${NC}"
    FAIL=$((FAIL+1))
fi

# =============================================================================
# 第四部分：SKILL-STANDARDS.md - 数据库设计标准
# =============================================================================
echo -e "\n${BLUE}${BOLD}【第四部分：数据库设计标准】${NC}"
echo "=================================================="

# 4.1 表结构字段列表
if grep -q "字段名.*类型.*长度\|字段列表" "$DOC"; then
    echo -e "${GREEN}✅ 表结构字段列表：已包含${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}❌ 表结构字段列表：缺失${NC}"
    FAIL=$((FAIL+1))
fi

# 4.2 索引设计
if grep -q "索引设计" "$DOC"; then
    echo -e "${GREEN}✅ 索引设计：已包含${NC}"
    PASS=$((PASS+1))
else
    echo -e "${YELLOW}⚠️  索引设计：建议补充${NC}"
    WARN=$((WARN+1))
fi

# 4.3 ER 图或表关系
if grep -q "ER 图\|表关系\|PK \|FK \|┌───.*│.*┌───" "$DOC"; then
    echo -e "${GREEN}✅ ER 图/表关系：已包含${NC}"
    PASS=$((PASS+1))
else
    echo -e "${YELLOW}⚠️  ER 图/表关系：建议补充${NC}"
    WARN=$((WARN+1))
fi

# 4.4 示例数据
if grep -q "INSERT INTO\|CREATE TABLE" "$DOC"; then
    echo -e "${GREEN}✅ 示例数据/DDL:已包含${NC}"
    PASS=$((PASS+1))
else
    echo -e "${YELLOW}⚠️  示例数据/DDL:建议补充${NC}"
    WARN=$((WARN+1))
fi

# =============================================================================
# =============================================================================
echo -e "\n${BLUE}${BOLD}【第五部分：三遍校验标准（独立验证）】${NC}"
echo "=================================================="

# 初始化独立评分（完全忽略文档中的评分）
REAL_SCORE=0

# -----------------------------------------------------------------------------
# 第一遍：需求→设计追溯（独立验证）
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}第一遍校验：需求→设计追溯（独立验证）${NC}"

# 1. 从文档提取需求章节号（从"需求原文"部分）
# 格式如：3.3.1、3.3.2 等
REQ_CHAPTERS=$(grep -oE "[0-9]+\.[0-9]+\.[0-9]+" "$DOC" 2>/dev/null | sort -u | wc -l | tr -d '[:space:]')

# 2. 检查每个需求是否有设计对应
REQ_COVERED=0

# 检查列表需求
if grep -q "列表" "$DOC"; then
    if grep -q "接口清单\|接口列表" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查创建需求
if grep -q "创建\|新增" "$DOC"; then
    if grep -q "POST\|新增" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查状态需求
if grep -q "状态" "$DOC"; then
    if grep -q "状态机\|状态流转" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查签名需求
if grep -q "签名" "$DOC"; then
    if grep -q "SM2\|Signature\|sign" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查版本需求
if grep -q "版本" "$DOC"; then
    if grep -q "version\|Version" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查终止需求
if grep -q "终止" "$DOC"; then
    if grep -q "Terminate\|终止" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查拒绝需求
if grep -q "拒绝" "$DOC"; then
    if grep -q "Reject\|拒绝" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查撤销需求
if grep -q "撤销" "$DOC"; then
    if grep -q "Revoke\|撤销" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查同步需求
if grep -q "同步" "$DOC"; then
    if grep -q "Sync\|同步" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查事件需求
if grep -q "事件" "$DOC"; then
    if grep -q "Event\|事件" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查履约需求
if grep -q "履约" "$DOC"; then
    if grep -q "fulfillment\|履约" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查详情需求
if grep -q "详情" "$DOC"; then
    if grep -q "detail\|详情" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 检查协商需求
if grep -q "协商" "$DOC"; then
    if grep -q "Negotiate\|协商" "$DOC"; then
        REQ_COVERED=$((REQ_COVERED+1))
    fi
fi

# 3. 计算覆盖度
if [ "$REQ_CHAPTERS" -gt 0 ]; then
    COVERAGE=$((REQ_COVERED * 100 / REQ_CHAPTERS))
else
    COVERAGE=0
fi

echo "  - 需求章节数：$REQ_CHAPTERS"
echo "  - 有设计对应的需求：$REQ_COVERED"
echo "  - 需求覆盖度：$COVERAGE%"

if [ "$COVERAGE" -ge 80 ]; then
    echo -e "${GREEN}✅ 第一遍校验：需求覆盖度$COVERAGE% (要求≥80%)${NC}"
else
    echo -e "${RED}❌ 第一遍校验：需求覆盖度$COVERAGE% (要求≥80%)${NC}"
fi

# -----------------------------------------------------------------------------
# 第二遍：设计→需求回溯（独立验证）
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}第二遍校验：设计→需求回溯（独立验证）${NC}"

# 1. 统计所有设计内容
DESIGN_COUNT=0
DESIGN_WITH_REQ=0

# 检查流程图
if grep -q "graph TD\|graph LR\|┌───.*│" "$DOC"; then
    DESIGN_COUNT=$((DESIGN_COUNT+1))
    if grep -q "流程.*需求\|需求.*流程" "$DOC"; then
        DESIGN_WITH_REQ=$((DESIGN_WITH_REQ+1))
    fi
fi

# 检查接口设计
INTERFACE_COUNT=$(grep -c "### $MODULE-API-" "$DOC" 2>/dev/null || echo "0")
INTERFACE_COUNT=$(echo "$INTERFACE_COUNT" | tr -d '[:space:]')
if [ "$INTERFACE_COUNT" -gt 0 ]; then
    DESIGN_COUNT=$((DESIGN_COUNT+1))
    DESIGN_WITH_REQ=$((DESIGN_WITH_REQ+1))
fi

# 检查核心逻辑
if grep -q "核心逻辑" "$DOC"; then
    DESIGN_COUNT=$((DESIGN_COUNT+1))
    if grep -q "需求依据\|从需求识别" "$DOC"; then
        DESIGN_WITH_REQ=$((DESIGN_WITH_REQ+1))
    fi
fi

# 检查数据库表
if grep -q "CREATE TABLE\|字段名.*类型" "$DOC"; then
    DESIGN_COUNT=$((DESIGN_COUNT+1))
    if grep -q "存储\|数据.*需求" "$DOC"; then
        DESIGN_WITH_REQ=$((DESIGN_WITH_REQ+1))
    fi
fi

# 2. 计算必要度
if [ "$DESIGN_COUNT" -gt 0 ]; then
    NECESSITY=$((DESIGN_WITH_REQ * 100 / DESIGN_COUNT))
else
    NECESSITY=0
fi

echo "  - 设计内容数：$DESIGN_COUNT"
echo "  - 有需求依据的设计：$DESIGN_WITH_REQ"
echo "  - 设计必要度：$NECESSITY%"

if [ "$NECESSITY" -ge 80 ]; then
    echo -e "${GREEN}✅ 第二遍校验：设计必要度$NECESSITY% (要求≥80%)${NC}"
else
    echo -e "${RED}❌ 第二遍校验：设计必要度$NECESSITY% (要求≥80%)${NC}"
fi

# -----------------------------------------------------------------------------
# 第三遍：完整性校验（独立验证）
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}第三遍校验：完整性校验（独立验证）${NC}"

COMPLETE_COUNT=0

# 4.1 完整性
PART_41=0
FLOW_STEPS=$(grep -E "^[[:space:]]*[0-9]+[.]" "$DOC" 2>/dev/null | wc -l | tr -d '[:space:]')

[ "$FLOW_COUNT" -ge 2 ] && PART_41=$((PART_41+1))
[ "$FLOW_STEPS" -ge 30 ] && PART_41=$((PART_41+1))
grep -q "字段流转" "$DOC" && PART_41=$((PART_41+1))
grep -q "状态机\|状态流转" "$DOC" && PART_41=$((PART_41+1))

if [ "$PART_41" -ge 3 ]; then
    echo -e "${GREEN}  ✅ 4.1 业务流程：完整 ($PART_41/4)${NC}"
    COMPLETE_COUNT=$((COMPLETE_COUNT+1))
else
    echo -e "${RED}  ❌ 4.1 业务流程：不完整 ($PART_41/4)${NC}"
fi

# 4.2 完整性
PART_42=0
grep -q "核心逻辑识别" "$DOC" && PART_42=$((PART_42+1))
CODE_BLOCKS=$(grep -c '\`\`\`java' "$DOC" 2>/dev/null || echo "0")
CODE_BLOCKS=$(echo "$CODE_BLOCKS" | tr -d '[:space:]')
[ "$CODE_BLOCKS" -ge 5 ] && PART_42=$((PART_42+1))
grep -q "业务规则实现位置" "$DOC" && PART_42=$((PART_42+1))

if [ "$PART_42" -ge 2 ]; then
    echo -e "${GREEN}  ✅ 4.2 核心逻辑设计：完整 ($PART_42/3)${NC}"
    COMPLETE_COUNT=$((COMPLETE_COUNT+1))
else
    echo -e "${RED}  ❌ 4.2 核心逻辑设计：不完整 ($PART_42/3)${NC}"
fi

# 4.3 完整性
PART_43=0
[ "$INTERFACE_COUNT" -ge 10 ] && PART_43=$((PART_43+1))
BASIC_INFO=$(grep -c "接口基本信息" "$DOC" 2>/dev/null || echo "0")
BASIC_INFO=$(echo "$BASIC_INFO" | tr -d '[:space:]')
[ "$BASIC_INFO" -ge "$INTERFACE_COUNT" ] && PART_43=$((PART_43+1))
ERROR_CODE=$(grep -c "错误码" "$DOC" 2>/dev/null || echo "0")
ERROR_CODE=$(echo "$ERROR_CODE" | tr -d '[:space:]')
[ "$ERROR_CODE" -ge 8 ] && PART_43=$((PART_43+1))

if [ "$PART_43" -ge 2 ]; then
    echo -e "${GREEN}  ✅ 4.3 接口设计：完整 ($PART_43/3)${NC}"
    COMPLETE_COUNT=$((COMPLETE_COUNT+1))
else
    echo -e "${RED}  ❌ 4.3 接口设计：不完整 ($PART_43/3)${NC}"
fi

# 4.4 完整性
PART_44=0
grep -q "字段名.*类型.*长度\|字段列表" "$DOC" && PART_44=$((PART_44+1))
grep -q "索引设计" "$DOC" && PART_44=$((PART_44+1))
grep -q "ER 图\|表关系" "$DOC" && PART_44=$((PART_44+1))
grep -q "INSERT INTO\|CREATE TABLE" "$DOC" && PART_44=$((PART_44+1))

if [ "$PART_44" -ge 3 ]; then
    echo -e "${GREEN}  ✅ 4.4 数据库设计：完整 ($PART_44/4)${NC}"
    COMPLETE_COUNT=$((COMPLETE_COUNT+1))
else
    echo -e "${RED}  ❌ 4.4 数据库设计：不完整 ($PART_44/4)${NC}"
fi

# 计算完整性百分比
if [ "$COMPLETE_COUNT" -eq 4 ]; then
    COMPLETENESS=100
    echo -e "${GREEN}✅ 第三遍校验：完整性 100%${NC}"
    REAL_SCORE=$((REAL_SCORE+10))
else
    COMPLETENESS=$((COMPLETE_COUNT * 25))
    echo -e "${RED}❌ 第三遍校验：完整性$COMPLETENESS% (要求 100%)${NC}"
fi

# -----------------------------------------------------------------------------
# 质量评分（完全独立计算，忽略文档中的评分）
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}质量评分（独立计算，忽略文档中的评分）${NC}"

# 重置 REAL_SCORE，完全独立计算

# 4.1 业务流程（25 分）
[ "$FLOW_COUNT" -ge 2 ] && REAL_SCORE=$((REAL_SCORE+10))
[ "$FLOW_STEPS" -ge 30 ] && REAL_SCORE=$((REAL_SCORE+10))
grep -q "字段流转" "$DOC" && REAL_SCORE=$((REAL_SCORE+5))

# 4.2 核心逻辑（25 分）
grep -q "核心逻辑识别" "$DOC" && REAL_SCORE=$((REAL_SCORE+10))
[ "$CODE_BLOCKS" -ge 5 ] && REAL_SCORE=$((REAL_SCORE+15))

# 4.3 接口设计（25 分）
[ "$INTERFACE_COUNT" -ge 10 ] && REAL_SCORE=$((REAL_SCORE+15))
[ "$ERROR_CODE" -ge 8 ] && REAL_SCORE=$((REAL_SCORE+10))

# 4.4 数据库设计（25 分）
grep -q "字段名.*类型.*长度\|字段列表" "$DOC" && REAL_SCORE=$((REAL_SCORE+10))
grep -q "索引设计" "$DOC" && REAL_SCORE=$((REAL_SCORE+10))
grep -q "ER 图\|表关系" "$DOC" && REAL_SCORE=$((REAL_SCORE+5))

echo -e "独立计算评分：${BOLD}$REAL_SCORE 分${NC} (要求≥85 分)"

if [ "$REAL_SCORE" -ge 85 ]; then
    echo -e "${GREEN}✅ 质量评分：$REAL_SCORE 分 (≥85 分)${NC}"
else
    echo -e "${RED}❌ 质量评分：$REAL_SCORE 分 (<85 分)${NC}"
fi

# =============================================================================
# 对比文档中的三遍校验内容（发现 AI 造假）
# =============================================================================
echo -e "\n${YELLOW}文档中的三遍校验内容检查（发现 AI 造假）${NC}"

# 提取文档中写的覆盖度
DOC_COVERAGE=$(grep -oP "需求覆盖度.*?\K[0-9]+" "$DOC" 2>/dev/null | head -1)
if [ -n "$DOC_COVERAGE" ] && [ "$DOC_COVERAGE" != "$COVERAGE" ]; then
    echo -e "${RED}⚠️  差异发现：文档声称需求覆盖度$DOC_COVERAGE%，实际$COVERAGE%${NC}"
fi

# 提取文档中写的必要度
DOC_NEC=$(grep -oP "设计必要度.*?\K[0-9]+" "$DOC" 2>/dev/null | head -1)
if [ -n "$DOC_NEC" ] && [ "$DOC_NEC" != "$NECESSITY" ]; then
    echo -e "${RED}⚠️  差异发现：文档声称设计必要度$DOC_NEC%，实际$NECESSITY%${NC}"
fi

# 提取文档中写的评分
DOC_SCORE=$(grep -oP "总分.*?\K[0-9]+" "$DOC" 2>/dev/null | tail -1)
if [ -n "$DOC_SCORE" ] && [ "$DOC_SCORE" != "$REAL_SCORE" ]; then
    echo -e "${RED}⚠️  差异发现：文档声称评分$DOC_SCORE 分，实际$REAL_SCORE 分${NC}"
    echo -e "${YELLOW}   说明：AI 可能在文档中虚报评分${NC}"
fi

# =============================================================================
# 最终判定：严格标准（95 分 + 100% 覆盖率）
# =============================================================================
echo ""
echo "=================================================="
echo -e "  ${BOLD}最终判定（严格标准）${NC}"
echo "=================================================="
echo ""

FINAL_PASS=1

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}❌ 判定失败：发现$FAIL 项验证问题${NC}"
    FINAL_PASS=0
fi

if [ $REAL_SCORE -lt 95 ]; then
    echo -e "${RED}❌ 判定失败：质量评分$REAL_SCORE 分 (<95 分)${NC}"
    FINAL_PASS=0
fi

if [ "$COVERAGE" -lt 100 ] 2>/dev/null; then
    echo -e "${RED}❌ 判定失败：需求覆盖度$COVERAGE% (<100%)${NC}"
    FINAL_PASS=0
fi

if [ "$NECESSITY" -lt 100 ] 2>/dev/null; then
    echo -e "${RED}❌ 判定失败：设计必要度$NECESSITY% (<100%)${NC}"
    FINAL_PASS=0
fi

echo ""

if [ $FINAL_PASS -eq 1 ]; then
    echo -e "${GREEN}${BOLD}✅ 最终判定通过：文档符合严格标准${NC}"
    echo ""
    echo "  - 质量评分：$REAL_SCORE 分 (≥95 分) ✓"
    echo "  - 需求覆盖度：$COVERAGE% (100%) ✓"
    echo "  - 设计必要度：$NECESSITY% (100%) ✓"
    echo ""
    echo "评级：AAA+ (卓越)"
    echo ""
    echo -e "${GREEN}→ 可以继续下一个模块${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}❌ 最终判定失败：文档不符合严格标准${NC}"
    echo ""
    echo "  - 质量评分：$REAL_SCORE 分 (要求≥95 分)"
    echo "  - 需求覆盖度：$COVERAGE% (要求 100%)"
    echo "  - 设计必要度：$NECESSITY% (要求 100%)"
    echo ""
    echo "评级：C (待改进)"
    echo ""
    echo -e "${YELLOW}${BOLD}【AI 重新设计要求】根据 skill.md 第 4 章要求：${NC}"
    echo ""
    echo "  1. 必须重新生成该模块的详细设计"
    echo "  2. 必须达到以下标准才能通过："
    echo "     - 质量评分 ≥ 95 分"
    echo "     - 需求覆盖度 = 100%"
    echo "     - 设计必要度 = 100%"
    echo "  3. 必须执行完整的 4.1→4.2→4.3→4.4→4.5 流程"
    echo "  4. 重新生成后必须再次执行验证脚本"
    echo ""
    echo -e "${RED}验证通过前不得进入下一模块${NC}"
    exit 1
fi
