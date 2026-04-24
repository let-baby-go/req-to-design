#!/usr/bin/env python3
"""
existing-apis.json 完整性验证脚本
用于第2章代码分析完成后的验证

验证内容：
1. 接口完整性验证 - 是否所有接口都输出
2. 8字段完整性验证 - 每个接口的8个字段是否完整
3. description质量验证 - 描述是否清晰、具体

使用方式：
    python verify_existing_apis.py <existing-apis.json路径>
"""

import json
import sys
import os
from datetime import datetime

REQUIRED_FIELDS = [
    "path",
    "method",
    "controller",
    "description",
    "calledClass",
    "entity",
    "params",
    "returns"
]

FUZZY_DESCRIPTIONS = [
    "定时任务",
    "接口",
    "方法",
    "功能",
    "操作",
    "处理",
    "TODO",
    "待补充",
    "暂无",
    "略",
    "同上",
    "见上文",
    "见下文"
]

MIN_DESC_LENGTH = 5

class ValidationResult:
    def __init__(self):
        self.pass_count = 0
        self.fail_count = 0
        self.warn_count = 0
        self.failures = []
        self.warnings = []
    
    def pass_(self, msg):
        self.pass_count += 1
        print(f"✅ {msg}")
    
    def fail(self, msg):
        self.fail_count += 1
        self.failures.append(msg)
        print(f"❌ {msg}")
    
    def warn(self, msg):
        self.warn_count += 1
        self.warnings.append(msg)
        print(f"⚠️  {msg}")
    
    def final_check(self):
        total = self.pass_count + self.fail_count + self.warn_count
        score = int(self.pass_count * 100 / total) if total > 0 else 0
        
        print("\n" + "=" * 60)
        print("📊 验证结果汇总")
        print("=" * 60)
        print(f"  - 通过项：{self.pass_count}")
        print(f"  - 失败项：{self.fail_count}")
        print(f"  - 警告项：{self.warn_count}")
        print(f"  - 质量评分：{score}%")
        print("=" * 60)
        
        if self.fail_count == 0 and score >= 90:
            print("\n✅ 最终判定：通过 (评级 A)")
            print("   可以继续进入 2.3 用户确认")
            return True
        elif self.fail_count > 0:
            print("\n❌ 最终判定：失败 (评级 C)")
            print("   必须重新执行第2章代码分析")
            return False
        else:
            print("\n⚠️  最终判定：待改进 (评级 B)")
            print("   建议修复警告项后继续")
            return True


def validate_json_file(filepath):
    """验证JSON文件是否存在且格式正确"""
    if not os.path.exists(filepath):
        print(f"❌ 文件不存在：{filepath}")
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        print(f"❌ JSON格式错误：{e}")
        return None


def validate_structure(data, result):
    """验证JSON结构是否正确"""
    print("\n" + "-" * 60)
    print("📋 结构验证")
    print("-" * 60)
    
    if "modules" not in data:
        result.fail("缺少 'modules' 字段")
        return False
    
    if not isinstance(data["modules"], dict):
        result.fail("'modules' 不是字典类型")
        return False
    
    if len(data["modules"]) == 0:
        result.fail("'modules' 为空，无模块数据")
        return False
    
    result.pass_(f"模块数量：{len(data['modules'])} 个")
    return True


def validate_module(module_name, module_data, result):
    """验证单个模块的接口"""
    print(f"\n📦 验证模块：{module_name}")
    print("-" * 40)
    
    if "apis" not in module_data:
        result.fail(f"模块 {module_name} 缺少 'apis' 字段")
        return 0
    
    apis = module_data["apis"]
    if not isinstance(apis, list):
        result.fail(f"模块 {module_name} 的 'apis' 不是列表类型")
        return 0
    
    if len(apis) == 0:
        result.fail(f"模块 {module_name} 的接口列表为空")
        return 0
    
    valid_count = 0
    
    for idx, api in enumerate(apis):
        api_result = validate_single_api(module_name, idx, api, result)
        if api_result:
            valid_count += 1
    
    result.pass_(f"模块 {module_name}：共 {len(apis)} 个接口，有效 {valid_count} 个")
    return valid_count


def validate_single_api(module_name, idx, api, result):
    """验证单个接口的8字段完整性"""
    api_id = f"{module_name}[{idx}]"
    
    missing_fields = []
    empty_fields = []
    placeholder_fields = []
    
    for field in REQUIRED_FIELDS:
        if field not in api:
            missing_fields.append(field)
        elif api[field] is None or api[field] == "":
            empty_fields.append(field)
        elif is_placeholder_value(api[field]):
            placeholder_fields.append(field)
    
    if missing_fields:
        result.fail(f"{api_id} 缺少字段：{', '.join(missing_fields)}")
        return False
    
    if empty_fields:
        result.fail(f"{api_id} 空字段：{', '.join(empty_fields)}")
        return False
    
    if placeholder_fields:
        result.warn(f"{api_id} 占位符字段：{', '.join(placeholder_fields)}")
    
    desc_quality = validate_description(api.get("description", ""), api_id, result)
    
    return len(missing_fields) == 0 and len(empty_fields) == 0


def is_placeholder_value(value):
    """检查是否为占位符值"""
    if isinstance(value, str):
        placeholders = ["TODO", "待补充", "暂无", "略", "TBD", "null", "NULL"]
        return any(p in value.upper() if p.upper() != "NULL" else p in value for p in placeholders)
    return False


def validate_description(description, api_id, result):
    """验证description质量"""
    if not description or len(description.strip()) == 0:
        result.fail(f"{api_id} description 为空")
        return "empty"
    
    desc = description.strip()
    
    if len(desc) < MIN_DESC_LENGTH:
        result.warn(f"{api_id} description 过短（<{MIN_DESC_LENGTH}字符）：'{desc}'")
        return "too_short"
    
    for fuzzy in FUZZY_DESCRIPTIONS:
        if fuzzy in desc and len(desc) < 20:
            result.warn(f"{api_id} description 包含模糊描述：'{fuzzy}' → '{desc}'")
            return "fuzzy"
    
    if has_meaningful_content(desc):
        result.pass_(f"{api_id} description 质量：合格 '{desc[:30]}...'")
        return "good"
    else:
        result.warn(f"{api_id} description 缺乏实质内容：'{desc}'")
        return "weak"


def has_meaningful_content(description):
    """检查description是否包含实质内容"""
    meaningful_keywords = [
        "查询", "创建", "新增", "修改", "更新", "删除", "获取", "提交",
        "签署", "推送", "接收", "同步", "下载", "上传", "导出", "导入",
        "分页", "详情", "列表", "统计", "校验", "验证", "认证", "授权",
        "数据源", "数据资源", "合约", "订单", "用户", "权限", "配置",
        "连接器", "主体", "身份", "证书", "密钥", "签名", "备案"
    ]
    
    for keyword in meaningful_keywords:
        if keyword in description:
            return True
    
    return False


def validate_interface_count(data, result):
    """验证接口总数是否合理"""
    print("\n" + "-" * 60)
    print("📊 接口统计验证")
    print("-" * 60)
    
    total_interfaces = 0
    module_interface_counts = []
    
    for module_name, module_data in data.get("modules", {}).items():
        api_count = len(module_data.get("apis", []))
        total_interfaces += api_count
        module_interface_counts.append((module_name, api_count))
    
    result.pass_(f"接口总数：{total_interfaces} 个")
    
    if total_interfaces < 10:
        result.fail(f"接口总数过少（<{10}个），可能存在遗漏")
    
    for module_name, count in module_interface_counts:
        if count < 3:
            result.warn(f"模块 {module_name} 接口数过少（{count}个）")
    
    return total_interfaces


def validate_field_statistics(data, result):
    """验证字段统计"""
    print("\n" + "-" * 60)
    print("📈 字段统计")
    print("-" * 60)
    
    field_stats = {field: {"present": 0, "empty": 0, "valid": 0} for field in REQUIRED_FIELDS}
    
    for module_name, module_data in data.get("modules", {}).items():
        for api in module_data.get("apis", []):
            for field in REQUIRED_FIELDS:
                if field in api:
                    field_stats[field]["present"] += 1
                    value = api[field]
                    if value is not None and value != "" and not is_placeholder_value(value):
                        field_stats[field]["valid"] += 1
                    else:
                        field_stats[field]["empty"] += 1
                else:
                    field_stats[field]["empty"] += 1
    
    total_interfaces = 0
    for module_data in data.get("modules", {}).values():
        total_interfaces += len(module_data.get("apis", []))
    
    print("\n字段完整性统计：")
    for field, stats in field_stats.items():
        presence_rate = stats["present"] * 100 // total_interfaces if total_interfaces > 0 else 0
        valid_rate = stats["valid"] * 100 // stats["present"] if stats["present"] > 0 else 0
        
        status = "✅" if presence_rate == 100 and valid_rate >= 90 else "❌"
        print(f"  {status} {field}: 存在率 {presence_rate}%，有效率 {valid_rate}%")
        
        if presence_rate < 100:
            result.fail(f"字段 '{field}' 存在率不足：{presence_rate}%")
        elif valid_rate < 90:
            result.warn(f"字段 '{field}' 有效率不足：{valid_rate}%")
        else:
            result.pass_(f"字段 '{field}' 完整")


def generate_report(data, result, output_dir):
    """生成验证报告"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "pass_count": result.pass_count,
            "fail_count": result.fail_count,
            "warn_count": result.warn_count,
            "quality_score": int(result.pass_count * 100 / (result.pass_count + result.fail_count + result.warn_count)) if (result.pass_count + result.fail_count + result.warn_count) > 0 else 0
        },
        "failures": result.failures,
        "warnings": result.warnings,
        "modules": {},
        "recommendations": []
    }
    
    for module_name, module_data in data.get("modules", {}).items():
        apis = module_data.get("apis", [])
        invalid_apis = []
        
        for idx, api in enumerate(apis):
            issues = []
            for field in REQUIRED_FIELDS:
                if field not in api:
                    issues.append(f"缺少字段: {field}")
                elif api[field] is None or api[field] == "":
                    issues.append(f"字段为空: {field}")
            
            if issues:
                invalid_apis.append({
                    "index": idx,
                    "controller": api.get("controller", "unknown"),
                    "issues": issues
                })
        
        report["modules"][module_name] = {
            "total_apis": len(apis),
            "invalid_apis": invalid_apis,
            "valid_rate": (len(apis) - len(invalid_apis)) * 100 // len(apis) if len(apis) > 0 else 0
        }
    
    if result.fail_count > 0:
        report["recommendations"].append("重新执行第2章代码分析，补充缺失字段")
    if result.warn_count > 0:
        report["recommendations"].append("检查警告项，提升description质量")
    
    report_path = os.path.join(output_dir, "existing-apis-validation-report.json")
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n📝 验证报告已保存：{report_path}")
    except Exception as e:
        print(f"⚠️  保存报告失败：{e}")
    
    return report


def main():
    if len(sys.argv) < 2:
        print("❌ 错误：请提供 existing-apis.json 文件路径")
        print("使用方式：python verify_existing_apis.py <文件路径>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    output_dir = os.path.dirname(filepath)
    if len(sys.argv) >= 3:
        output_dir = sys.argv[2]
    
    print("=" * 60)
    print("📋 existing-apis.json 完整性验证")
    print("=" * 60)
    print(f"文件路径：{filepath}")
    print(f"验证时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    data = validate_json_file(filepath)
    if data is None:
        sys.exit(1)
    
    result = ValidationResult()
    
    if not validate_structure(data, result):
        sys.exit(1)
    
    total_valid = 0
    for module_name, module_data in data.get("modules", {}).items():
        valid_count = validate_module(module_name, module_data, result)
        total_valid += valid_count
    
    validate_interface_count(data, result)
    validate_field_statistics(data, result)
    
    report = generate_report(data, result, output_dir)
    
    passed = result.final_check()
    
    if passed:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()