#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controller和Task接口提取脚本
提取8个字段：path, method, controller, description, params, returns, calledClass, entity
entity字段通过扫描项目实体类并分析ServiceImpl方法体提取
"""

import os
import re
import json
from pathlib import Path

# 配置
PROJECT_PATH = "/Library/zData/idea/skill_train"
OUTPUT_FILE = "/Users/zhangwanyu/Downloads/skill_result/7/context/existing-apis.json"

# 模块配置
MODULES = [
    {
        "name": "dataqin-data-bridge",
        "path": "/Library/zData/idea/skill_train/dataqin-data-bridge",
        "type": "controller"
    },
    {
        "name": "dataqin-quartz",
        "path": "/Library/zData/idea/skill_train/dataqin-quartz",
        "type": "task"
    }
]

# 实体类扫描配置（通用配置）
ENTITY_DIRS = ["entity", "domain", "model", "po"]  # 实体类常见目录名
ENTITY_ANNOTATIONS = ["@TableName", "@Entity", "@Table", "@MappedSuperclass"]  # 实体类常见注解
VO_SUFFIXES = ["Vo", "DTO", "Param", "Query", "Request", "Response"]  # 需排除的Vo类后缀


class ApiExtractor:
    """接口提取器"""

    def __init__(self):
        self.apis = []  # 兼容旧逻辑，存储所有接口
        self.module_apis = {}  # 按模块分类存储接口
        self.current_module = ""  # 当前处理的模块名称
        self.entity_names = set()  # 实体类名字典
        self.service_impl_cache = {}  # ServiceImpl文件缓存
        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "skipped_files": 0,
            "total_apis": 0,
            "entity_found_count": 0
        }

    def extract_all(self):
        """提取所有模块的接口"""
        print("【开始提取接口信息】")

        # 步骤0：扫描所有模块的实体类（通用扫描）
        print("\n【扫描项目实体类】")
        for module in MODULES:
            self._scan_entity_classes(module['path'])
        print(f"发现实体类总数：{len(self.entity_names)}")
        if len(self.entity_names) > 0:
            print(f"示例实体类：{list(self.entity_names)[:10]}")

        for module in MODULES:
            self.current_module = module['name']
            self.module_apis[self.current_module] = []  # 初始化模块接口列表
            print(f"\n处理模块：{module['name']}")

            if module['type'] == 'controller':
                self._extract_controllers(module)
            elif module['type'] == 'task':
                self._extract_tasks(module)

        print(f"\n【提取完成】")
        print(f"处理文件总数：{self.stats['processed_files']}")
        print(f"跳过文件总数：{self.stats['skipped_files']}")
        print(f"提取接口总数：{self.stats['total_apis']}")
        print(f"entity提取成功数：{self.stats['entity_found_count']}")

        # 保存结果
        self._save_results()

    def _extract_controllers(self, module):
        """提取Controller模块的接口"""
        module_path = module['path']

        # 扫描所有Controller文件
        controller_files = []
        for root, dirs, files in os.walk(module_path):
            for file in files:
                if file.endswith('Controller.java'):
                    controller_files.append(os.path.join(root, file))

        self.stats['total_files'] += len(controller_files)
        print(f"发现 {len(controller_files)} 个Controller文件")

        for file_path in controller_files:
            self._process_controller_file(file_path, module['path'])

    def _scan_entity_classes(self, module_path):
        """扫描项目实体类（通用方法）"""
        print(f"  扫描路径：{module_path}")

        # 方法1：扫描实体类目录
        for entity_dir in ENTITY_DIRS:
            pattern = os.path.join(module_path, "**", entity_dir, "*.java")
            for root, dirs, files in os.walk(module_path):
                # 检查当前目录名是否匹配
                if os.path.basename(root) == entity_dir:
                    for file in files:
                        if file.endswith('.java'):
                            class_name = file.replace('.java', '')
                            # 排除Vo类后缀
                            if not any(class_name.endswith(suffix) for suffix in VO_SUFFIXES):
                                self.entity_names.add(class_name)

        # 方法2：扫描带实体类注解的文件
        for root, dirs, files in os.walk(module_path):
            for file in files:
                if file.endswith('.java'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read(500)  # 只读取前500字符，检查注解
                            # 检查是否包含实体类注解
                            if any(ann in content for ann in ENTITY_ANNOTATIONS):
                                class_name = file.replace('.java', '')
                                # 排除Vo类后缀
                                if not any(class_name.endswith(suffix) for suffix in VO_SUFFIXES):
                                    self.entity_names.add(class_name)
                    except:
                        pass

    def _extract_entity_from_returns(self, returns_str):
        """从returns字段提取entity（CommonResult<XxxVo> -> Xxx）"""
        if not returns_str:
            return ""
        
        # 提取泛型中的类名
        generic_pattern = r'<(\w+)>'
        matches = re.findall(generic_pattern, returns_str)
        
        found_entities = []
        for class_name in matches:
            # 处理Vo类：ServerInformationVo -> ServerInformation
            entity_name = class_name
            for suffix in VO_SUFFIXES:
                if class_name.endswith(suffix):
                    entity_name = class_name[:-len(suffix)]
                    break
            
            if entity_name in self.entity_names and entity_name not in found_entities:
                found_entities.append(entity_name)
            
            # 也检查原始类名
            if class_name in self.entity_names and class_name not in found_entities:
                found_entities.append(class_name)
        
        return ','.join(found_entities) if found_entities else ""

    def _find_service_impl_file(self, called_class, module_path):
        """根据calledClass定位ServiceImpl文件"""
        if not called_class:
            return None

        # calledClass格式：Impl类名.方法名，如 TransferNegotiationServiceImpl.pullData
        # 提取类名
        if '.' in called_class:
            impl_name = called_class.split('.')[0]
        else:
            impl_name = called_class

        # 在项目中搜索ServiceImpl文件（精确匹配）
        for root, dirs, files in os.walk(module_path):
            for file in files:
                if file == impl_name + '.java':
                    return os.path.join(root, file)

        # 尝试后缀匹配
        for root, dirs, files in os.walk(module_path):
            for file in files:
                if file.endswith(impl_name + '.java'):
                    return os.path.join(root, file)

        return None

    def _extract_entity_from_service_impl(self, service_impl_file, called_class, called_class_original):
        """从ServiceImpl方法体提取entity"""
        if not service_impl_file:
            return ""

        # 缓存ServiceImpl文件内容
        if service_impl_file not in self.service_impl_cache:
            try:
                with open(service_impl_file, 'r', encoding='utf-8') as f:
                    self.service_impl_cache[service_impl_file] = f.read()
            except:
                return ""

        content = self.service_impl_cache[service_impl_file]

        # 从calledClass提取方法名（格式：Impl类名.方法名）
        if '.' in called_class:
            method_name = called_class.split('.')[1]
        else:
            method_name = called_class_original  # 备用

        # 提取方法体
        method_body = self._extract_service_method_body(content, method_name)
        if not method_body:
            # 尝试从整个ServiceImpl中匹配entity
            return self._match_entities_in_code(content)

        return self._match_entities_in_code(method_body)

    def _extract_service_method_body(self, content, method_name):
        """从ServiceImpl中提取指定方法的方法体"""
        # 匹配方法签名：public + 返回类型 + 方法名 + 参数 + {
        pattern = rf'public\s+\w+[<\w>,\s]*?\s+{method_name}\s*\([^)]*\)\s*\{{'
        match = re.search(pattern, content)
        if not match:
            return ""

        body_start = match.end() - 1
        return self._extract_complete_method_body(content, body_start)

    def _match_entities_in_code(self, code):
        """在代码中匹配实体类名"""
        found_entities = []

        # 优先级1：返回类型中的entity（包括Controller方法的返回类型）
        # 匹配：CommonResult<XxxVo> -> Xxx, List<Xxx> -> Xxx
        # 提取泛型中的类名
        generic_pattern = r'<(\w+)>'
        generic_matches = re.findall(generic_pattern, code)
        for class_name in generic_matches:
            # 处理Vo类：ServerInformationVo -> ServerInformation
            entity_name = class_name
            for suffix in VO_SUFFIXES:
                if class_name.endswith(suffix):
                    entity_name = class_name[:-len(suffix)]
                    break
            
            if entity_name in self.entity_names and entity_name not in found_entities:
                found_entities.append(entity_name)
            # 也检查原始类名是否是实体
            if class_name in self.entity_names and class_name not in found_entities:
                found_entities.append(class_name)

        # 优先级2：方法参数中的entity
        # 匹配：(Xxx xxx) 或 (List<Xxx> xxx)
        param_pattern = r'\((\w+)[<\s,]'
        param_matches = re.findall(param_pattern, code)
        for class_name in param_matches:
            entity_name = class_name
            for suffix in VO_SUFFIXES:
                if class_name.endswith(suffix):
                    entity_name = class_name[:-len(suffix)]
                    break
            
            if entity_name in self.entity_names and entity_name not in found_entities:
                found_entities.append(entity_name)

        # 优先级3：Mapper调用中的entity
        # 匹配：xxxMapper.insert(xxx) 或 xxxMapper.selectList(...)
        mapper_pattern = r'(\w+)Mapper\.\w+\((\w+)'
        mapper_matches = re.findall(mapper_pattern, code)
        for prefix, entity_var in mapper_matches:
            # prefix通常是entity名的小写，如applicationMapper
            entity_name = prefix.capitalize()
            if entity_name in self.entity_names and entity_name not in found_entities:
                found_entities.append(entity_name)

        # 优先级4：new语句中的entity
        new_pattern = r'new\s+(\w+)\s*\('
        new_matches = re.findall(new_pattern, code)
        for class_name in new_matches:
            entity_name = class_name
            for suffix in VO_SUFFIXES:
                if class_name.endswith(suffix):
                    entity_name = class_name[:-len(suffix)]
                    break
            
            if entity_name in self.entity_names and entity_name not in found_entities:
                found_entities.append(entity_name)

        # 优先级5：return语句中的entity
        # 匹配：return xxx; 或 return new Xxx();
        return_pattern = r'return\s+(?:new\s+)?(\w+)\s*[;(<]'
        return_matches = re.findall(return_pattern, code)
        for class_name in return_matches:
            entity_name = class_name
            for suffix in VO_SUFFIXES:
                if class_name.endswith(suffix):
                    entity_name = class_name[:-len(suffix)]
                    break
            
            if entity_name in self.entity_names and entity_name not in found_entities:
                found_entities.append(entity_name)

        # 多个entity用逗号串联
        if found_entities:
            return ','.join(found_entities)

        return ""

    def _process_controller_file(self, file_path, module_path):
        """处理单个Controller文件"""
        self.stats['processed_files'] += 1
        file_name = os.path.basename(file_path)
        print(f"  处理 [{self.stats['processed_files']}/{self.stats['total_files']}]: {file_name}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if content.strip().startswith('/*'):
                print(f"    跳过（文件被注释）")
                self.stats['skipped_files'] += 1
                return

            class_info = self._extract_class_info(content)
            if not class_info:
                print(f"    跳过（无法提取类信息）")
                self.stats['skipped_files'] += 1
                return

            methods = self._extract_methods(content)

            for method_info in methods:
                entity = ""
                
                # 来源1：Controller方法体直接提取
                entity = method_info.get('entity_from_controller', "")
                
                # 来源2：从returns字段提取
                if not entity:
                    entity = self._extract_entity_from_returns(method_info['returns'])
                
                # 来源3：从ServiceImpl方法体提取
                if not entity and method_info['called_class']:
                    # called_class格式：Impl类名.方法名
                    service_impl_file = self._find_service_impl_file(
                        method_info['called_class'], 
                        module_path
                    )
                    if service_impl_file:
                        # 从called_class中提取方法名
                        method_name_from_called = method_info['called_class'].split('.')[-1] if '.' in method_info['called_class'] else method_info['method_name']
                        entity = self._extract_entity_from_service_impl(
                            service_impl_file,
                            method_info['called_class'],
                            method_name_from_called
                        )

                if entity:
                    self.stats['entity_found_count'] += 1

                api = {
                    "path": self._build_url(class_info['base_url'], method_info['url']),
                    "method": method_info['http_method'],
                    "controller": class_info['class_name'],
                    "description": self._build_description(
                        class_info['api_tag'],
                        method_info['java_doc'],
                        method_info['api_operation']
                    ),
                    "calledClass": method_info['called_class'],
                    "entity": entity,
                    "params": method_info['params'],
                    "returns": method_info['returns']
                }
                self.apis.append(api)
                self.module_apis[self.current_module].append(api)
                self.stats['total_apis'] += 1

            print(f"    提取 {len(methods)} 个接口")

        except Exception as e:
            import traceback
            print(f"    错误：{e}")
            traceback.print_exc()
            self.stats['skipped_files'] += 1

    def _extract_class_info(self, content):
        """提取类级信息"""
        class_info = {}

        # 提取类名
        class_match = re.search(r'public\s+class\s+(\w+Controller)', content)
        if class_match:
            class_info['class_name'] = class_match.group(1)
        else:
            return None

        # 提取类级@RequestMapping
        request_mapping_match = re.search(r'@RequestMapping\s*\(\s*"([^"]+)"\s*\)', content)
        if request_mapping_match:
            class_info['base_url'] = request_mapping_match.group(1)
        else:
            class_info['base_url'] = ""

        # 提取@Api(tags)
        api_tag_match = re.search(r'@Api\s*\(\s*tags\s*=\s*"([^"]+)"\s*\)', content)
        if api_tag_match:
            class_info['api_tag'] = api_tag_match.group(1)
        else:
            class_info['api_tag'] = ""

        return class_info

    def _extract_methods(self, content):
        """提取所有方法信息"""
        methods = []
        
        class_match = re.search(r'public\s+class\s+\w+.*?\{', content, re.MULTILINE)
        if not class_match:
            return methods
        
        class_body_start = class_match.end()
        method_positions = []
        i = class_body_start
        
        while i < len(content):
            if content[i:i+7] == 'public ' and content[i:i+13] != 'public class':
                sig_start = i
                brace_pos = content.find('{', i)
                if brace_pos == -1:
                    i += 1
                    continue
                
                sig_text = content[i:brace_pos]
                
                # 找方法名后的第一个(
                paren_count = 0
                first_method_paren = -1
                for j, char in enumerate(sig_text):
                    if char == '(':
                        if paren_count == 0:
                            first_method_paren = j
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
                
                if first_method_paren == -1:
                    i += 1
                    continue
                
                before_paren = sig_text[:first_method_paren].strip()
                words = before_paren.split()
                if len(words) < 2:
                    i += 1
                    continue
                
                method_name = words[-1]
                return_type = ' '.join(words[:-1]).replace('public ', '').strip()
                
                # 提取参数部分（从第一个(到最后的)，用括号计数）
                params_start = first_method_paren + 1
                paren_count = 1
                params_end = -1
                for j in range(params_start, len(sig_text)):
                    if sig_text[j] == '(':
                        paren_count += 1
                    elif sig_text[j] == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            params_end = j
                            break
                
                params_str = sig_text[params_start:params_end] if params_end != -1 else ""
                
                method_positions.append({
                    'start': sig_start,
                    'body_start': brace_pos,
                    'return_type': return_type,
                    'method_name': method_name,
                    'params_str': params_str,
                })
                
                i = brace_pos + 1
            else:
                i += 1
        
        prev_boundary = class_body_start
        
        for method_pos in method_positions:
            annotation_area = content[prev_boundary:method_pos['start']]
            method_body = self._extract_complete_method_body(content, method_pos['body_start'])
            prev_boundary = method_pos['body_start'] + len(method_body)
            
            method_info = {}
            method_info['method_name'] = method_pos['method_name']
            
            javadoc_match = re.search(r'/\*\*(?:[^*]|\*(?!/))*\*/', annotation_area, re.DOTALL)
            javadoc_raw = javadoc_match.group(0) if javadoc_match else ""
            java_doc = self._clean_javadoc(javadoc_raw) if javadoc_raw else ""
            method_info['java_doc'] = java_doc
            
            http_method, url = self._extract_http_method_and_url(annotation_area)
            method_info['http_method'] = http_method
            method_info['url'] = url
            
            api_operation = self._extract_api_operation_safe(annotation_area)
            method_info['api_operation'] = api_operation
            
            # 提取参数类型
            params = self._extract_param_types(method_pos['params_str'])
            method_info['params'] = params
            
            method_info['returns'] = method_pos['return_type']
            
            called_class = self._extract_called_class(method_body)
            method_info['called_class'] = called_class
            
            entity = self._match_entities_in_code(method_body)
            method_info['entity_from_controller'] = entity
            
            methods.append(method_info)
        
        return methods
    
    def _extract_param_types(self, params_str):
        """从参数字符串提取参数类型"""
        if not params_str.strip():
            return []
        
        params = []
        # 分割参数（按逗号分割，但要处理泛型中的逗号）
        # 简化：按逗号分割，然后提取类型
        
        # 方法：遍历字符，遇到逗号且括号计数为0时分割
        paren_count = 0
        param_parts = []
        current_part = ""
        
        for char in params_str:
            if char == '(' or char == '<':
                paren_count += 1
                current_part += char
            elif char == ')' or char == '>':
                paren_count -= 1
                current_part += char
            elif char == ',' and paren_count == 0:
                param_parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
        
        if current_part.strip():
            param_parts.append(current_part.strip())
        
        # 提取每个参数的类型
        for part in param_parts:
            # 格式：@Annotation Type name
            # 或：Type name
            words = part.split()
            if not words:
                continue
            
            # 过滤掉注解（以@开头的）
            type_words = [w for w in words if not w.startswith('@')]
            
            if type_words:
                # 类型通常是倒数第二个词（最后一个词是参数名）
                # 但可能有多个注解，所以取第一个非注解词
                param_type = type_words[0]
                # 去掉可能的final关键字
                if param_type == 'final':
                    param_type = type_words[1] if len(type_words) > 1 else ""
                
                if param_type:
                    params.append(param_type)
        
        return params
    
    def _extract_api_operation_safe(self, annotation_area):
        """安全提取@ApiOperation value"""
        idx = annotation_area.find('@ApiOperation')
        if idx == -1:
            return ""
        
        value_idx = annotation_area.find('value', idx)
        if value_idx == -1:
            return ""
        
        quote_idx = annotation_area.find('"', value_idx)
        if quote_idx == -1:
            return ""
        
        end_quote_idx = annotation_area.find('"', quote_idx + 1)
        if end_quote_idx == -1:
            return ""
        
        return annotation_area[quote_idx + 1:end_quote_idx]

    def _extract_called_class(self, method_body):
        """从方法体提取调用的Service类和方法名，转换为ServiceImpl类名.方法名格式"""
        service_pattern = r'(\w+)\.(\w+)\('
        all_matches = re.findall(service_pattern, method_body)

        if not all_matches:
            return ""

        non_service_keywords = [
            'CommonResult', 'commonResult', 'AjaxResult', 'ajaxResult',
            'log', 'logger', 'Log', 'LOGGER',
            'System', 'Math', 'Collections', 'Arrays', 'StringUtils', 'JSON',
            'result', 'response', 'return', 'param', 'wrapper',
            'page', 'file', 'path', 'url', 'out', 'Arrays',
            'this'
        ]

        service_matches = [(field, method) for field, method in all_matches 
                          if 'Service' in field and field not in non_service_keywords]

        if service_matches:
            field_name, method_name = service_matches[-1]
            
            if field_name.endswith('Service'):
                base_name = field_name[:-7]
            else:
                base_name = field_name
            
            impl_name = base_name[0].upper() + base_name[1:] + 'ServiceImpl'
            return f"{impl_name}.{method_name}"

        potential_services = [(field, method) for field, method in all_matches 
                             if field not in non_service_keywords 
                             and not field.startswith('get')
                             and not field.startswith('set')
                             and not field.startswith('is')
                             and len(field) > 3]

        if potential_services:
            field_name, method_name = potential_services[-1]
            if field_name.endswith('Service'):
                base_name = field_name[:-7]
                impl_name = base_name[0].upper() + base_name[1:] + 'ServiceImpl'
                return f"{impl_name}.{method_name}"
            return f"{field_name}.{method_name}"

        return ""

    def _extract_complete_method_body(self, content, body_start):
        """提取完整方法体（处理嵌套大括号）"""
        brace_count = 0
        i = body_start
        max_length = 5000  # 最大提取长度

        while i < len(content) and i < body_start + max_length:
            char = content[i]

            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    # 方法体结束
                    return content[body_start:i+1]

            i += 1

        # 如果未找到匹配的结束括号，返回最大长度内容
        return content[body_start:body_start + max_length]

    def _extract_http_method_and_url(self, annotations):
        """提取HTTP方法和URL（支持简单格式和复杂格式）"""
        # @GetMapping - 简单格式：@GetMapping("/xxx")
        get_match_simple = re.search(r'@GetMapping\s*\(\s*"([^"]+)"\s*\)', annotations)
        if get_match_simple:
            return "GET", get_match_simple.group(1)
        # @GetMapping - 复杂格式：@GetMapping(value = "/xxx", ...)
        get_match_complex = re.search(r'@GetMapping\s*\(\s*value\s*=\s*"([^"]+)"\s*', annotations)
        if get_match_complex:
            return "GET", get_match_complex.group(1)
        # @GetMapping - 无括号格式
        get_match_no_paren = re.search(r'@GetMapping\b(?!\s*\()', annotations)
        if get_match_no_paren:
            return "GET", ""

        # @PostMapping - 简单格式：@PostMapping("/xxx")
        post_match_simple = re.search(r'@PostMapping\s*\(\s*"([^"]+)"\s*\)', annotations)
        if post_match_simple:
            return "POST", post_match_simple.group(1)
        # @PostMapping - 复杂格式：@PostMapping(value = "/xxx", consumes = ...)
        post_match_complex = re.search(r'@PostMapping\s*\(\s*value\s*=\s*"([^"]+)"\s*', annotations)
        if post_match_complex:
            return "POST", post_match_complex.group(1)
        # @PostMapping - 无括号格式
        post_match_no_paren = re.search(r'@PostMapping\b(?!\s*\()', annotations)
        if post_match_no_paren:
            return "POST", ""

        # @PutMapping - 简单格式
        put_match_simple = re.search(r'@PutMapping\s*\(\s*"([^"]+)"\s*\)', annotations)
        if put_match_simple:
            return "PUT", put_match_simple.group(1)
        # @PutMapping - 复杂格式
        put_match_complex = re.search(r'@PutMapping\s*\(\s*value\s*=\s*"([^"]+)"\s*', annotations)
        if put_match_complex:
            return "PUT", put_match_complex.group(1)
        # @PutMapping - 无括号格式
        put_match_no_paren = re.search(r'@PutMapping\b(?!\s*\()', annotations)
        if put_match_no_paren:
            return "PUT", ""

        # @DeleteMapping - 简单格式
        delete_match_simple = re.search(r'@DeleteMapping\s*\(\s*"([^"]+)"\s*\)', annotations)
        if delete_match_simple:
            return "DELETE", delete_match_simple.group(1)
        # @DeleteMapping - 复杂格式
        delete_match_complex = re.search(r'@DeleteMapping\s*\(\s*value\s*=\s*"([^"]+)"\s*', annotations)
        if delete_match_complex:
            return "DELETE", delete_match_complex.group(1)
        # @DeleteMapping - 无括号格式
        delete_match_no_paren = re.search(r'@DeleteMapping\b(?!\s*\()', annotations)
        if delete_match_no_paren:
            return "DELETE", ""

        # @PatchMapping - 简单格式
        patch_match_simple = re.search(r'@PatchMapping\s*\(\s*"([^"]+)"\s*\)', annotations)
        if patch_match_simple:
            return "PATCH", patch_match_simple.group(1)
        # @PatchMapping - 复杂格式
        patch_match_complex = re.search(r'@PatchMapping\s*\(\s*value\s*=\s*"([^"]+)"\s*', annotations)
        if patch_match_complex:
            return "PATCH", patch_match_complex.group(1)
        # @PatchMapping - 无括号格式
        patch_match_no_paren = re.search(r'@PatchMapping\b(?!\s*\()', annotations)
        if patch_match_no_paren:
            return "PATCH", ""

        # @RequestMapping - 格式：@RequestMapping(value = "/xxx", method = RequestMethod.POST)
        request_match = re.search(r'@RequestMapping\s*\(\s*value\s*=\s*"([^"]+)"\s*,\s*method\s*=\s*RequestMethod\.(\w+)\s*\)', annotations)
        if request_match:
            return request_match.group(2), request_match.group(1)

        # 默认
        return "", ""

    def _extract_javadoc_before_method(self, content, method_start):
        """提取方法前的JavaDoc注释"""
        # 向前查找，直到找到上一个方法或类开始
        search_start = max(0, method_start - 2000)
        before_content = content[search_start:method_start]

        # 提取最近的JavaDoc注释（使用re.DOTALL匹配多行）
        javadoc_pattern = r'/\*\*(.*?)\*/'
        javadoc_matches = re.findall(javadoc_pattern, before_content, re.DOTALL)

        if javadoc_matches:
            # 取最后一个JavaDoc
            javadoc_raw = javadoc_matches[-1]
            # 清理JavaDoc格式
            javadoc_clean = self._clean_javadoc(javadoc_raw)
            return javadoc_clean

        return ""

    def _clean_javadoc(self, javadoc_raw):
        """清理JavaDoc注释"""
        if not javadoc_raw:
            return ""
        # 去除/* */和*前缀
        lines = javadoc_raw.strip().split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith('*'):
                line = line[1:].strip()
            if line and not line.startswith('@'):
                cleaned_lines.append(line)
        return ' '.join(cleaned_lines)

    def _extract_tasks(self, module):
        """提取Task模块的接口"""
        module_path = module['path']

        # 扫描所有Task文件（排除ScheduledInitTask）
        task_files = []
        for root, dirs, files in os.walk(module_path):
            for file in files:
                if file.endswith('Task.java') and file != 'ScheduledInitTask.java':
                    task_files.append(os.path.join(root, file))

        self.stats['total_files'] += len(task_files)
        print(f"发现 {len(task_files)} 个Task文件")

        for file_path in task_files:
            self._process_task_file(file_path, module_path)

    def _process_task_file(self, file_path, module_path):
        """处理单个Task文件"""
        self.stats['processed_files'] += 1
        file_name = os.path.basename(file_path)
        print(f"  处理 [{self.stats['processed_files']}/{self.stats['total_files']}]: {file_name}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            class_info = self._extract_task_class_info(content)
            if not class_info:
                print(f"    跳过（无法提取类信息）")
                self.stats['skipped_files'] += 1
                return

            methods = self._extract_task_methods(content)

            for method_info in methods:
                entity = method_info.get('entity_from_task', "")
                
                if not entity and method_info['called_class']:
                    service_impl_file = self._find_service_impl_file(
                        method_info['called_class'], 
                        module_path
                    )
                    if service_impl_file:
                        method_name_from_called = method_info['called_class'].split('.')[-1] if '.' in method_info['called_class'] else method_info['method_name']
                        entity = self._extract_entity_from_service_impl(
                            service_impl_file,
                            method_info['called_class'],
                            method_name_from_called
                        )

                if entity:
                    self.stats['entity_found_count'] += 1

                api = {
                    "path": class_info['component_name'],
                    "method": method_info['method_name'],
                    "controller": class_info['class_name'],
                    "description": method_info['java_doc'],
                    "calledClass": method_info['called_class'],
                    "entity": entity,
                    "params": method_info['params'],
                    "returns": method_info['returns']
                }
                self.apis.append(api)
                self.module_apis[self.current_module].append(api)
                self.stats['total_apis'] += 1

            print(f"    提取 {len(methods)} 个任务方法")

        except Exception as e:
            print(f"    错误：{e}")
            self.stats['skipped_files'] += 1

    def _extract_task_class_info(self, content):
        """提取Task类信息"""
        class_info = {}

        # 提取类名
        class_match = re.search(r'public\s+class\s+(\w+Task)', content)
        if class_match:
            class_info['class_name'] = class_match.group(1)
        else:
            return None

        # 提取@Component名称
        component_match = re.search(r'@Component\s*\(\s*"([^"]+)"\s*\)', content)
        if component_match:
            class_info['component_name'] = component_match.group(1)
        else:
            # 默认使用类名首字母小写
            class_name = class_info['class_name']
            class_info['component_name'] = class_name[0].lower() + class_name[1:]

        return class_info

    def _extract_task_methods(self, content):
        """提取Task的所有public方法"""
        methods = []

        # 找到所有方法签名位置（包含JavaDoc）
        method_signatures = []
        # 修正：使用更精确的JavaDoc匹配，支持多行
        signature_pattern = r'(/\*\*(?:[^*]|\*(?!/))*\*/)?\s*public\s+(\w+)\s+(\w+)\s*\(([^)]*)\)\s*\{'
        
        for match in re.finditer(signature_pattern, content, re.MULTILINE | re.DOTALL):
            javadoc_raw = match.group(1) or ""
            return_type = match.group(2)
            method_name = match.group(3)
            params_str = match.group(4)
            body_start = match.end() - 1
            
            method_signatures.append({
                'javadoc_raw': javadoc_raw,
                'return_type': return_type,
                'method_name': method_name,
                'params_str': params_str,
                'body_start': body_start
            })

        # 逐个提取完整方法体
        for sig in method_signatures:
            method_body = self._extract_complete_method_body(content, sig['body_start'])

            method_info = {}
            method_info['method_name'] = sig['method_name']

            # 清理JavaDoc
            if sig['javadoc_raw']:
                method_info['java_doc'] = self._clean_javadoc(sig['javadoc_raw'])
            else:
                method_info['java_doc'] = ""

            # 参数类型
            params = self._extract_param_types(sig['params_str'])
            method_info['params'] = params

            # 返回类型
            method_info['returns'] = sig['return_type']

            # calledClass
            called_class = self._extract_called_class_from_task(method_body)
            method_info['called_class'] = called_class
            
            # 从Task方法体中直接提取entity
            entity = self._match_entities_in_code(method_body)
            method_info['entity_from_task'] = entity
            
            methods.append(method_info)
        
        return methods
    
    def _extract_called_class_from_task(self, method_body):
        """从Task方法体提取调用的Service类和方法名"""
        service_pattern = r'(\w+)\.(\w+)\('
        all_matches = re.findall(service_pattern, method_body)

        if not all_matches:
            return ""

        non_service_keywords = [
            'CommonResult', 'commonResult', 'AjaxResult', 'ajaxResult',
            'log', 'logger', 'Log', 'LOGGER', 'redis', 'redisLock',
            'System', 'out', 'StringUtils', 'JSON', 'Collections',
            'this'
        ]

        service_matches = [(field, method) for field, method in all_matches 
                          if 'Service' in field and field not in non_service_keywords]

        if service_matches:
            field_name, method_name = service_matches[-1]
            
            if field_name.endswith('Service'):
                base_name = field_name[:-7]
            else:
                base_name = field_name
            
            impl_name = base_name[0].upper() + base_name[1:] + 'ServiceImpl'
            return f"{impl_name}.{method_name}"

        potential_services = [(field, method) for field, method in all_matches 
                             if field not in non_service_keywords and len(field) > 3]

        if potential_services:
            field_name, method_name = potential_services[-1]
            if field_name.endswith('Service'):
                base_name = field_name[:-7]
                impl_name = base_name[0].upper() + base_name[1:] + 'ServiceImpl'
                return f"{impl_name}.{method_name}"
            return f"{field_name}.{method_name}"

        return ""

    def _build_url(self, base_url, method_url):
        """构建完整URL"""
        if base_url and method_url:
            return base_url + method_url
        elif method_url:
            return method_url
        elif base_url:
            return base_url
        else:
            return ""

    def _build_description(self, api_tag, java_doc, api_operation):
        """拼接完整的description"""
        parts = []

        if api_tag:
            parts.append(f"[类级]{api_tag}")

        if java_doc:
            parts.append(f"[方法]{java_doc}")

        if api_operation:
            parts.append(f"[注解]{api_operation}")

        if parts:
            return " | ".join(parts)
        else:
            return ""

    def _save_results(self):
        """保存提取结果（输出modules结构，每个模块包含apis字段）"""
        # 转换结构：每个模块需要包含apis字段
        formatted_modules = {}
        for module_name, apis_list in self.module_apis.items():
            formatted_modules[module_name] = {
                "apis": apis_list
            }
        
        output_data = {
            "modules": formatted_modules,
            "stats": self.stats,
            "generatedAt": "2026-04-20T17:45:00"
        }

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n结果已保存到：{OUTPUT_FILE}")
        print(f"文件大小：{os.path.getsize(OUTPUT_FILE)} 字节")


if __name__ == "__main__":
    extractor = ApiExtractor()
    extractor.extract_all()