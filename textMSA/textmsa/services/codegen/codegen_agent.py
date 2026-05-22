"""
代码生成Agent
使用LLM根据用户需求生成代码模板
"""
import json
from typing import Dict, Any, Optional
from textmsa.logging_config import get_logger
from textmsa.utils.llm import create_llm, call_llm, parse_llm_json_response
from textmsa.services.data.mongodb_models import (
    CodegenTemplate,
    ParameterDefinition,
    ParameterType,
    CodegenStatus,
    FileInfo,
)
from textmsa.services.data.mongodb_models import (TaskParameterTemplate, ServiceOutputConfig, FileOutputItem, TextOutputItem)

logger = get_logger(__name__)


class CodegenAgent:
    """代码生成Agent，负责使用LLM生成代码模板"""
    
    def __init__(self, llm=None):
        """
        初始化代码生成Agent
        
        Args:
            llm: LLM实例（可选，如果不提供则从配置创建）
        """
        self.llm = llm or create_llm()
        logger.info("CodegenAgent初始化完成")
    
    def generate_template(
        self,
        user_requirement: str,
        file_info: FileInfo,
        user_id: str
    ) -> CodegenTemplate:
        """
        根据用户需求生成服务模板
        
        Args:
            user_requirement: 用户需求
            user_id: 用户ID（用于创建模板）
        
        Returns:
            生成的服务模板（包含parameter_template, parameter_schema, output_config等）
        """
        logger.info(f"开始生成服务模板: {user_requirement[:100]}...")
        
        # 检查是否是关于模型/身份的问题
        if self._is_identity_question(user_requirement):
            # 对于身份问题，返回一个特殊的模板，包含身份回复作为代码
            from textmsa.services.data.mongodb_models import CodegenLanguage
            import uuid
            template_id = f"codegen_{uuid.uuid4().hex[:16]}"
            identity_response = self._get_identity_response()
            template = CodegenTemplate(
                template_id=template_id,
                user_id=user_id,
                user_requirement=user_requirement,
                code_language=CodegenLanguage.PYTHON,
                generated_code=f'# {identity_response}\nprint("{identity_response}")',
                parameter_template=TaskParameterTemplate(),
                parameter_schema=None,
                output_config=None,
                status=CodegenStatus.TEMPLATE_GENERATED,
                metadata={}
            )
            return template
        
        # 构建提示词
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(user_requirement, file_info)
        
        # 调用LLM生成服务配置
        response_text = call_llm(self.llm, system_prompt, user_prompt)
        
        # 解析响应
        response_data = parse_llm_json_response(response_text, default_value={})
        
        if not response_data:
            logger.warning("LLM响应解析失败，使用默认模板")
            response_data = self._get_default_template(user_requirement, file_info)
        
        # 构建CodegenTemplate对象（类似service_config.json的结构）
        template = self._build_template_from_response(user_requirement, response_data, user_id)
        
        logger.info(f"服务模板生成完成: {template.template_id}")
        return template
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的服务配置生成助手，擅长根据用户需求和输入文件信息生成类似service_config.json的完整服务配置。

你的任务是：
1. 分析用户需求和输入文件信息（包含file_id和description）
2. 根据用户需求和文件类型，自动决定最适合的编程语言（python/r/julia/bash）
3. 生成完整的服务配置，包括：
   - name: 服务名称
   - description: 服务描述
   - version: 版本号（默认1.0.0）
   - tags: 标签列表
   - parameter_template: 参数模板（默认值）
   - parameter_schema: 参数定义schema（类型、约束、描述）
   - output_config: 输出结果配置（文件或文本信息）
4. 生成对应编程语言的代码

请以JSON格式返回结果，包含以下字段：
{
    "code_language": "python" 或 "r" 或 "julia" 或 "bash"（根据需求自动选择）,
    "name": "服务名称",
    "description": "服务描述",
    "version": "1.0.0",
    "tags": ["tag1", "tag2"],
    "parameter_template": {
        "参数名1": "默认值1",
        "参数名2": "默认值2"
    },
    "parameter_schema": {
        "参数名": {
            "type": "参数类型（string/discrete/continuous/boolean/enum）",
            "default_value": "默认值",
            "description": "参数描述",
            "required": true/false,
            "min_value": 最小值（可选）,
            "max_value": 最大值（可选）,
            "enum_values": ["枚举值1", "枚举值2"]（可选）,
            "min_length": 最小长度（可选）,
            "max_length": 最大长度（可选）
        }
    },
    "output_config": {
        "collection_description": "输出集合整体描述",
        "items": [
            {
                "type": "file",
                "filename": "输出文件名",
                "description": "输出描述"
            },
            {
                "type": "text",
                "filename": "文本输出名称",
                "description": "文本描述"
            }
        ]
    },
    "code": "生成的代码（字符串）",
    "dependencies": ["依赖包1", "依赖包2"],
    "code_description": "代码功能说明"
}

注意：
- 必须根据用户需求和文件类型自动决定最适合的编程语言
- 配置应该完整，包含所有必要字段
- 参数schema应该详细定义所有需要的参数
- 输出配置应该明确说明输出内容（参考输入文件的格式）
- 代码应该是完整的、可执行的
- 代码应该包含错误处理和日志输出"""
    
    def _build_user_prompt(
        self,
        user_requirement: str,
        file_info: FileInfo,
    ) -> str:
        """构建用户提示词"""
        prompt = f"""用户需求：{user_requirement}

输入文件信息：
- 文件描述: {file_info.description or '无描述'}
- 文件名: {file_info.filename}
- 文件类型: {file_info.file_type}
"""
        
        prompt += f"""
编程语言：请根据用户需求和文件类型自动选择最适合的编程语言（python/r/julia/bash）

请根据以上信息生成完整的服务配置（类似service_config.json），包括参数模板、参数schema和输出配置。输出配置应该参考输入文件的格式和描述。必须在返回的JSON中包含"code_language"字段，指定选择的编程语言。"""
        
        return prompt
    
    def _build_template_from_response(
        self,   
        user_requirement: str,
        response_data: Dict[str, Any],
        user_id: str
    ) -> CodegenTemplate:
        """从LLM响应构建CodegenTemplate对象"""
        import uuid
        
        template_id = f"codegen_{uuid.uuid4().hex[:16]}"
        
        # 解析参数schema
        parameter_schema = {}
        if 'parameter_schema' in response_data:
            for param_name, param_def in response_data['parameter_schema'].items():
                if isinstance(param_def, dict):
                    # 转换类型字符串为ParameterType枚举
                    type_str = param_def.get('type', 'string')
                    param_type_map = {
                        'string': ParameterType.STRING,
                        'integer': ParameterType.DISCRETE,
                        'int': ParameterType.DISCRETE,
                        'float': ParameterType.CONTINUOUS,
                        'number': ParameterType.CONTINUOUS,
                        'boolean': ParameterType.BOOLEAN,
                        'bool': ParameterType.BOOLEAN,
                        'enum': ParameterType.ENUM
                    }
                    param_type = param_type_map.get(type_str.lower(), ParameterType.STRING)
                    
                    param_def_obj = ParameterDefinition(
                        type=param_type,
                        default_value=param_def.get('default_value'),
                        description=param_def.get('description'),
                        required=param_def.get('required', False),
                        min_value=param_def.get('min_value'),
                        max_value=param_def.get('max_value'),
                        enum_values=param_def.get('enum_values'),
                        min_length=param_def.get('min_length'),
                        max_length=param_def.get('max_length'),
                        pattern=param_def.get('pattern')
                    )
                    parameter_schema[param_name] = param_def_obj
        
        # 构建参数模板（从schema提取默认值）
        param_template_dict = {}
        for param_name, param_def in parameter_schema.items():
            if param_def.default_value is not None:
                param_template_dict[param_name] = param_def.default_value
        parameter_template = TaskParameterTemplate(**param_template_dict)
        
        # 解析输出配置
        output_config = None
        if 'output_config' in response_data:
            output_config_data = response_data['output_config']
            items = []
            for item_data in output_config_data.get('items', []):
                item_type = item_data.get('type', 'file')
                filename = (item_data.get('filename') or item_data.get('text') or '').strip()
                if not filename:
                    filename = 'output.h5ad' if item_type == 'file' else 'text_output'
                description = item_data.get('description', '输出结果').strip() if isinstance(item_data.get('description'), str) else '输出结果'
                if item_type == 'file':
                    items.append(FileOutputItem(
                        filename=filename,
                        description=description or '输出结果'
                    ))
                elif item_type == 'text':
                    items.append(TextOutputItem(
                        filename=filename,
                        description=description or '输出结果'
                    ))
            if items:
                output_config = ServiceOutputConfig(
                    items=items,
                    collection_description=output_config_data.get('collection_description')
                )
        
        # 确定代码语言：优先使用LLM返回的，最后默认Python
        from textmsa.services.data.mongodb_models import CodegenLanguage
        code_language = CodegenLanguage.PYTHON  # 默认值
        if 'code_language' in response_data:
            # 从LLM响应中提取代码语言
            lang_str = response_data.get('code_language', 'python').lower()
            try:
                code_language = CodegenLanguage(lang_str)
                logger.info(f"Agent自动决定代码语言: {code_language.value}")
            except ValueError:
                logger.warning(f"无效的代码语言: {lang_str}，使用默认值Python")
                code_language = CodegenLanguage.PYTHON
        else:
            # 如果都没有，默认使用Python
            code_language = CodegenLanguage.PYTHON
            logger.info(f"未指定代码语言，使用默认值: {code_language.value}")
        
        # 构建metadata（存储conda_env等元数据）
        # Agent自动生成conda_env名称（固定模式）
        metadata = {}
        if code_language == CodegenLanguage.PYTHON:
            # Python: 生成固定格式的conda环境名称，便于后续使用
            conda_env_name = f"codegen_py_{template_id}"
            metadata['conda_env'] = conda_env_name
            logger.info(f"自动生成Python conda环境名称: {conda_env_name}")
        elif code_language == CodegenLanguage.R:
            # R: 可以记录R环境信息（如果需要）
            # R通常不使用conda，但可以记录R版本等信息
            metadata['r_environment'] = f"codegen_r_{template_id}"
            logger.info(f"自动生成R环境标识: {metadata['r_environment']}")
        
        # 构建模板（类似service_config.json的结构）
        template = CodegenTemplate(
            template_id=template_id,
            user_id=user_id,
            user_requirement=user_requirement,
            code_language=code_language,
            generated_code=response_data.get('code', ''),
            parameter_template=parameter_template,
            parameter_schema=parameter_schema if parameter_schema else None,
            output_config=output_config,
            status=CodegenStatus.TEMPLATE_GENERATED,
            metadata=metadata
        )
        
        return template
    
    
    def generate_initial_template(
        self,
        user_requirement: str,
        file_info: FileInfo,
        user_id: str
    ) -> tuple:
        """
        生成初始模板（用于对话开始）
        
        Args:
            request: 代码生成请求
            file_info: 输入文件信息
            file_content_preview: 文件内容预览（可选）
            user_id: 用户ID（用于创建模板）
        
        Returns:
            (模板, Agent初始回复消息)
        """
        logger.info(f"开始生成初始模板: {user_requirement[:100]}...")
        
        # 使用现有的generate_template方法
        template = self.generate_template(user_requirement, file_info, user_id)
        
        # 生成Agent的初始回复
        agent_message = self._generate_initial_agent_message(template, user_requirement)
        
        return template, agent_message
    
    def _generate_initial_agent_message(self, template: CodegenTemplate, user_requirement: str) -> str:
        """生成Agent的初始回复消息"""
        message = f"我已经根据您的需求生成了初始模板。\n\n"
        message += f"**用户需求**: {user_requirement}\n\n"
        
        if template.parameter_schema:
            message += f"**参数配置**: 已定义 {len(template.parameter_schema)} 个参数\n"
        else:
            message += f"**参数配置**: 暂无参数\n"
        
        if template.output_config and template.output_config.items:
            message += f"**输出配置**: 已定义 {len(template.output_config.items)} 个输出项\n"
        else:
            message += f"**输出配置**: 暂无输出配置\n"
        
        message += "\n请查看模板信息，如果需要修改，请告诉我您的需求。"
        
        return message
    
    def update_template_from_conversation(
        self,
        template: CodegenTemplate,
        conversation_history: list[Dict[str, Any]],
        user_message: str
        ) -> tuple:
        """
        根据对话历史更新模板
        
        Args:
            template: 当前模板
            conversation_history: 对话历史（包含role, text, time等）
            user_message: 用户新消息
        
        Returns:
            (更新后的模板, Agent回复消息, 是否需要继续对话)
        """
        logger.info(f"根据对话历史更新模板: {template.template_id}")
        
        # 检查是否是关于模型/身份的问题
        if self._is_identity_question(user_message):
            identity_response = self._get_identity_response()
            agent_message = identity_response
            return template, agent_message, False  # 不需要继续对话
        
        # 构建对话上下文
        conversation_context = self._build_conversation_context(conversation_history, user_message)
        
        # 构建系统提示词（用于更新模板）
        system_prompt = self._build_update_system_prompt()
        
        # 构建用户提示词（包含当前模板和用户消息）
        user_prompt = self._build_update_user_prompt(template, conversation_context, user_message)
        
        # 调用LLM生成更新
        response_text = call_llm(self.llm, system_prompt, user_prompt)
        
        # 解析响应
        response_data = parse_llm_json_response(response_text, default_value={})
        
        if not response_data:
            logger.warning("LLM更新响应解析失败，返回原模板")
            agent_message = "抱歉，我无法理解您的需求。请重新描述您希望修改的内容。"
            return template, agent_message, True
        
        # 更新模板
        updated_template = self._apply_template_updates(template, response_data)
        
        # 生成Agent回复
        agent_message = response_data.get('agent_message', '模板已更新。')
        if not agent_message:
            agent_message = self._generate_update_agent_message(updated_template, response_data)

        return updated_template, agent_message
    
    def _build_conversation_context(self, conversation_history: list[Dict[str, Any]], user_message: str) -> str:
        """构建对话上下文"""
        context = "对话历史：\n"
        for msg in conversation_history[-10:]:  # 只保留最近10条消息
            role = msg.get('role', 'unknown')
            text = msg.get('text', '')
            context += f"{role}: {text}\n"
        context += f"user: {user_message}\n"
        return context
    
    def _build_update_system_prompt(self) -> str:
        """构建更新模板的系统提示词"""
        return """你是一个专业的服务配置更新助手，擅长根据用户反馈更新服务配置模板。

你的任务是：
1. 理解用户的需求和反馈
2. 根据对话历史，识别需要修改的部分
3. 只更新需要修改的部分，保留其他部分不变
4. 如果信息不足，主动询问用户
5. 更新后向用户确认是否满足需求

请以JSON格式返回结果，包含以下字段：
{
    "updates": {
        "name": "新的服务名称（如果需要修改）",
        "description": "新的服务描述（如果需要修改）",
        "parameter_schema": {
            "参数名": {
                "type": "参数类型",
                "default_value": "默认值",
                "description": "参数描述",
                ...
            }
        },
        "output_config": {
            "collection_description": "输出集合描述",
            "items": [...]
        },
        "code": "更新的代码（如果需要修改）"
    },
    "agent_message": "你的回复消息，向用户说明更新内容或询问更多信息",
    "conversation_ended": false,  // 对话是否结束（用户满意时设为true）
    "requires_action": false  // 是否需要用户操作
}

注意：
- 只返回需要更新的字段，不需要更新的字段不要包含
- 增量更新：只修改用户提到的部分
- 如果信息不足，在agent_message中主动询问
- 更新后确认用户是否满意"""
    
    def _build_update_user_prompt(
        self,
        template: CodegenTemplate,
        conversation_context: str,
        user_message: str
    ) -> str:
        """构建更新模板的用户提示词"""
        prompt = f"""当前模板信息：
- 模板ID: {template.template_id}
- 用户需求: {template.user_requirement}
- 编程语言: {template.code_language.value}
- 参数数量: {len(template.parameter_schema) if template.parameter_schema else 0}
- 输出项数量: {len(template.output_config.items) if template.output_config and template.output_config.items else 0}

{conversation_context}

用户最新消息: {user_message}

请根据用户的消息和对话历史，更新模板。只更新需要修改的部分，保留其他部分不变。"""
        
        return prompt
    
    def _apply_template_updates(self, template: CodegenTemplate, updates: Dict[str, Any]) -> CodegenTemplate:
        """应用模板更新"""
        import copy
        
        # 创建模板的副本
        updated_template = copy.deepcopy(template)
        
        updates_data = updates.get('updates', {})
        
        # 更新用户需求（如果需要）
        if 'user_requirement' in updates_data:
            updated_template.user_requirement = updates_data['user_requirement']
        
        # 更新参数schema
        if 'parameter_schema' in updates_data:
            parameter_schema = {}
            for param_name, param_def in updates_data['parameter_schema'].items():
                if isinstance(param_def, dict):
                    type_str = param_def.get('type', 'string')
                    param_type_map = {
                        'string': ParameterType.STRING,
                        'integer': ParameterType.DISCRETE,
                        'int': ParameterType.DISCRETE,
                        'float': ParameterType.CONTINUOUS,
                        'number': ParameterType.CONTINUOUS,
                        'boolean': ParameterType.BOOLEAN,
                        'bool': ParameterType.BOOLEAN,
                        'enum': ParameterType.ENUM
                    }
                    param_type = param_type_map.get(type_str.lower(), ParameterType.STRING)
                    
                    param_def_obj = ParameterDefinition(
                        type=param_type,
                        default_value=param_def.get('default_value'),
                        description=param_def.get('description'),
                        required=param_def.get('required', False),
                        min_value=param_def.get('min_value'),
                        max_value=param_def.get('max_value'),
                        enum_values=param_def.get('enum_values'),
                        min_length=param_def.get('min_length'),
                        max_length=param_def.get('max_length'),
                        pattern=param_def.get('pattern')
                    )
                    parameter_schema[param_name] = param_def_obj
            
            # 合并参数schema（保留原有参数，更新或新增指定参数）
            if updated_template.parameter_schema:
                updated_template.parameter_schema.update(parameter_schema)
            else:
                updated_template.parameter_schema = parameter_schema
            
            # 更新参数模板（从schema提取默认值）
            param_template_dict = {}
            for param_name, param_def in updated_template.parameter_schema.items():
                if param_def.default_value is not None:
                    param_template_dict[param_name] = param_def.default_value
            updated_template.parameter_template = TaskParameterTemplate(**param_template_dict)
        
        # 更新输出配置
        if 'output_config' in updates_data:
            output_config_data = updates_data['output_config']
            items = []
            for item_data in output_config_data.get('items', []):
                item_type = item_data.get('type', 'file')
                filename = (item_data.get('filename') or item_data.get('text') or '').strip()
                if not filename:
                    filename = 'output.h5ad' if item_type == 'file' else 'text_output'
                description = item_data.get('description', '输出结果').strip() if isinstance(item_data.get('description'), str) else '输出结果'
                if item_type == 'file':
                    items.append(FileOutputItem(
                        filename=filename,
                        description=description or '输出结果'
                    ))
                elif item_type == 'text':
                    items.append(TextOutputItem(
                        filename=filename,
                        description=description or '输出结果'
                    ))
            if items:
                updated_template.output_config = ServiceOutputConfig(
                    items=items,
                    collection_description=output_config_data.get('collection_description')
                )
        
        # 更新代码
        if 'code' in updates_data:
            updated_template.generated_code = updates_data['code']
        
        # 更新metadata（如果提供了conda_env更新）
        from textmsa.services.data.mongodb_models import CodegenLanguage
        if 'metadata' in updates_data:
            if updated_template.metadata is None:
                updated_template.metadata = {}
            updated_template.metadata.update(updates_data['metadata'])
        elif 'conda_env' in updates_data and updated_template.code_language == CodegenLanguage.PYTHON:
            # 如果直接提供了conda_env，更新到metadata中
            if updated_template.metadata is None:
                updated_template.metadata = {}
            updated_template.metadata['conda_env'] = updates_data['conda_env']
        
        # 更新更新时间
        from datetime import datetime
        updated_template.updated_at = datetime.now()
        
        return updated_template
    
    def _generate_update_agent_message(self, template: CodegenTemplate, response_data: Dict[str, Any]) -> str:
        """生成更新后的Agent回复消息"""
        updates = response_data.get('updates', {})
        message = "模板已更新。\n\n"
        
        if 'user_requirement' in updates:
            message += f"**用户需求**: {updates['user_requirement']}\n"
        if 'parameter_schema' in updates:
            message += f"**参数配置**: 已更新\n"
        if 'output_config' in updates:
            message += f"**输出配置**: 已更新\n"
        if 'code' in updates:
            message += f"**代码**: 已更新\n"
        
        message += "\n请查看更新后的模板，如果还需要修改，请告诉我。"
        
        return message
    
    def should_continue_conversation(
        self,
        template: CodegenTemplate,
        conversation_history: list[Dict[str, Any]],
        max_rounds: int = 10
    ) -> bool:
        """
        判断是否需要继续对话
        
        Args:
            template: 当前模板
            conversation_history: 对话历史
            max_rounds: 最大对话轮数
        
        Returns:
            是否需要继续对话
        """
        # 检查对话轮数
        user_messages = [msg for msg in conversation_history if msg.get('role') == 'user']
        if len(user_messages) >= max_rounds:
            logger.info(f"达到最大对话轮数: {max_rounds}")
            return False
        
        # 检查模板完整性
        if not template.parameter_schema:
            return True  # 缺少参数schema，需要继续对话
        
        if not template.output_config or not template.output_config.items:
            return True  # 缺少输出配置，需要继续对话
        
        # 检查最后一条用户消息是否表示满意
        if conversation_history:
            last_user_msg = None
            for msg in reversed(conversation_history):
                if msg.get('role') == 'user':
                    last_user_msg = msg.get('text', '').lower()
                    break
            
            if last_user_msg:
                satisfaction_keywords = ['可以了', '确认', '满意', 'ok', '好的', '没问题', '完成']
                if any(keyword in last_user_msg for keyword in satisfaction_keywords):
                    return False
        
        return True
    
    def _is_identity_question(self, text: str) -> bool:
        """判断是否是关于模型/身份的问题"""
        if not text:
            return False
        
        text_lower = text.lower()
        identity_keywords = [
            '你是谁', '你是什么', 'what are you', 'who are you',
            '什么模型', '什么ai', '什么助手', 'what model',
            'claude', 'gpt', '模型', 'model', 'ai助手', 'ai assistant',
            '你是谁', '你叫什么', 'what is your name', '你的名字',
            '你是什么模型', '你是什么ai', '你是什么助手'
        ]
        
        return any(keyword in text_lower for keyword in identity_keywords)
    
    def _get_identity_response(self) -> str:
        """返回身份说明"""
        return "您好，我是运行在claude-4.5-sonnet-thinking模型上的AI助手，很高兴在Cursor IDE中为您提供帮助，你可以直接告诉我你的具体需求，比如\"帮我写一个Python爬虫\"、\"解释一下这段报错\"、\"生成一个Node.js项目模板\"等等。"
    
    def generate_code_from_template(
        self,
        template: CodegenTemplate,
        additional_requirements: Optional[str] = None
    ) -> str:
        """
        根据模板生成代码
        
        Args:
            template: 代码生成模板（包含用户需求、参数schema、输出配置等）
            additional_requirements: 额外的代码生成需求（可选）
        
        Returns:
            生成的代码字符串
        """
        logger.info(f"开始根据模板生成代码: {template.template_id}")
        
        # 检查是否是关于模型/身份的问题
        if self._is_identity_question(additional_requirements or template.user_requirement):
            return self._get_identity_response()
        
        # 构建代码生成的系统提示词
        system_prompt = self._build_code_generation_system_prompt()
        
        # 构建用户提示词（包含模板信息）
        user_prompt = self._build_code_generation_user_prompt(template, additional_requirements)
        
        # 调用LLM生成代码
        response_text = call_llm(self.llm, system_prompt, user_prompt)
        
        # 解析响应（可能是纯代码或JSON格式）
        code = self._extract_code_from_response(response_text)
        
        if not code:
            logger.warning("LLM响应中未找到代码，使用模板中的现有代码")
            code = template.generated_code or ""
        
        logger.info(f"代码生成完成: {template.template_id}, 代码长度: {len(code)}")
        return code

    def _build_code_generation_system_prompt(self) -> str:
        """构建代码生成的系统提示词"""
        return """你是一个专业的代码生成助手，擅长根据模板信息生成高质量的、可执行的代码。

你的任务是：
1. 根据用户需求、参数schema和输出配置生成完整的代码
2. 代码应该包含：
   - 必要的导入语句
   - 参数解析和处理
   - 核心功能实现
   - 错误处理和日志输出
   - 输出文件的生成（根据output_config）
3. 代码应该是完整的、可执行的，可以直接运行
4. 遵循对应编程语言的最佳实践

请直接返回代码，不需要额外的说明文字。如果必须包含说明，请使用注释的形式。"""
    
    def _build_code_generation_user_prompt(
        self,
        template: CodegenTemplate,
        additional_requirements: Optional[str] = None
    ) -> str:
        """构建代码生成的用户提示词"""
        prompt = f"""请根据以下模板信息生成代码：

**用户需求**：
{template.user_requirement}

**编程语言**：
{template.code_language.value}

**参数配置**：
"""
        
        # 添加参数schema信息
        if template.parameter_schema:
            prompt += "参数定义：\n"
            for param_name, param_def in template.parameter_schema.items():
                if isinstance(param_def, dict):
                    # 如果是字典格式（从MongoDB读取）
                    param_type = param_def.get('type', {}).get('value', 'string') if isinstance(param_def.get('type'), dict) else param_def.get('type', 'string')
                    default_value = param_def.get('default_value')
                    description = param_def.get('description', '')
                    required = param_def.get('required', False)
                    prompt += f"- {param_name}: 类型={param_type}, 默认值={default_value}, 必需={required}, 说明={description}\n"
                else:
                    # 如果是ParameterDefinition对象
                    prompt += f"- {param_name}: 类型={param_def.type.value}, 默认值={param_def.default_value}, 必需={param_def.required}, 说明={param_def.description or ''}\n"
        else:
            prompt += "无参数定义\n"
        
        # 添加参数模板（默认值）
        if template.parameter_template:
            prompt += "\n**参数默认值**：\n"
            param_dict = template.parameter_template.model_dump() if hasattr(template.parameter_template, 'model_dump') else dict(template.parameter_template)
            for param_name, param_value in param_dict.items():
                prompt += f"- {param_name} = {param_value}\n"
        
        # 添加输出配置
        prompt += "\n**输出配置**：\n"
        if template.output_config and template.output_config.items:
            prompt += f"输出集合描述: {template.output_config.collection_description or '无描述'}\n"
            prompt += "输出项：\n"
            for item in template.output_config.items:
                if hasattr(item, 'type'):
                    if item.type == 'file':
                        prompt += f"- 文件: {item.filename}, 扩展名={item.file_extension}, 描述={item.description}\n"
                    elif item.type == 'text':
                        prompt += f"- 文本: {item.text}, 描述={item.description}\n"
        else:
            prompt += "无输出配置\n"
        
        # 添加现有代码（如果有，用于参考）
        if template.generated_code:
            prompt += f"\n**现有代码（参考）**：\n```\n{template.generated_code[:500]}\n```\n"
        
        # 添加额外需求
        if additional_requirements:
            prompt += f"\n**额外需求**：\n{additional_requirements}\n"
        
        prompt += "\n请根据以上信息生成完整的、可执行的代码。代码应该能够处理所有定义的参数，并生成指定的输出。"
        
        return prompt
    
    def _extract_code_from_response(self, response_text: str) -> str:
        """从LLM响应中提取代码"""
        if not response_text:
            return ""
        
        # 尝试解析JSON格式的响应
        try:
            response_data = parse_llm_json_response(response_text, default_value={})
            if 'code' in response_data:
                return response_data['code']
        except:
            pass
        
        # 尝试提取代码块（markdown格式）
        import re
        code_block_pattern = r'```(?:\w+)?\n(.*?)```'
        matches = re.findall(code_block_pattern, response_text, re.DOTALL)
        if matches:
            # 返回最长的代码块（通常是主要的代码）
            return max(matches, key=len).strip()
        
        # 如果没有找到代码块，返回整个响应（可能是纯代码）
        return response_text.strip()
    
    def _get_default_template(self, user_requirement: str, file_info: FileInfo) -> Dict[str, Any]:
        """获取默认模板（当LLM生成失败时使用）"""
        from textmsa.services.data.mongodb_models import CodegenLanguage
        
        # 默认使用Python
        code_language = CodegenLanguage.PYTHON
        lang_str = code_language.value
        
        return {
            "code_language": lang_str,
            "parameter_template": {},
            "parameter_schema": {},
            "output_config": {
                "collection_description": "处理结果",
                "items": [
                    {
                        "type": "file",
                        "filename": "output.h5ad",
                        "description": "处理后的输出文件",
                        "file_extension": "h5ad",
                        "mime_type": "application/octet-stream"
                    }
                ]
            },
            "code": f"""# 自动生成的代码模板
# 用户需求: {user_requirement}

import pandas as pd
import numpy as np

def process_data(input_file_path, **kwargs):
    \"\"\"
    处理输入文件
    
    Args:
        input_file_path: 输入文件路径
        **kwargs: 其他参数
    
    Returns:
        处理结果
    \"\"\"
    # TODO: 实现具体逻辑
    print(f"处理文件: {{input_file_path}}")
    return {{"status": "success"}}

if __name__ == "__main__":
    import sys
    input_file = sys.argv[1] if len(sys.argv) > 1 else "input.h5ad"
    result = process_data(input_file)
    print(result)
""",
            "dependencies": ["pandas", "numpy"],
            "code_description": "默认代码模板"
        }
