from typing import Optional, List, Dict, Any
from openai import OpenAI
import google.generativeai as genai
from backend.config import config
import json

class AIClient:
    def __init__(self):
        self._openai_clients = {}
        self._gemini_models = {}

    def _get_openai_client(self, model_config: dict) -> OpenAI:
        """获取或创建 OpenAI 兼容客户端（支持 DeepSeek、Ollama、OpenAI 等）"""
        base_url = model_config.get('base_url', 'https://api.openai.com/v1')

        if base_url not in self._openai_clients:
            self._openai_clients[base_url] = OpenAI(
                api_key=model_config['api_key'],
                base_url=base_url
            )
        return self._openai_clients[base_url]

    def _get_gemini_model(self, model_config: dict):
        """获取或创建 Gemini 模型"""
        model_name = model_config.get('model', 'gemini-2.0-flash-exp')

        if model_name not in self._gemini_models:
            genai.configure(api_key=model_config['api_key'])
            self._gemini_models[model_name] = genai.GenerativeModel(model_name)
        return self._gemini_models[model_name]

    def generate(self, prompt: str, purpose: str, system_prompt: Optional[str] = None,
                 tools: Optional[List[Dict]] = None) -> str:
        """根据用途生成文本

        Args:
            prompt: 用户提示词
            purpose: 用途（profile_generation, reply_generation, embedding）
            system_prompt: 系统提示词
            tools: Function calling 工具定义
        """
        model_config = config.get_model_config(purpose)
        provider = model_config.get('provider')

        if provider == 'openai_compatible':
            return self._generate_with_openai(prompt, model_config, system_prompt, tools)
        elif provider == 'gemini':
            return self._generate_with_gemini(prompt, model_config, system_prompt, tools)
        else:
            raise ValueError(f"不支持的提供商: {provider}")

    def _generate_with_openai(self, prompt: str, model_config: dict,
                              system_prompt: Optional[str] = None,
                              tools: Optional[List[Dict]] = None) -> Any:
        client = self._get_openai_client(model_config)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model_config['model'],
            "messages": messages,
            "temperature": model_config.get('temperature', 0.7)
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)

        if tools and response.choices[0].message.tool_calls:
            return response.choices[0].message

        return response.choices[0].message.content

    def _generate_with_gemini(self, prompt: str, model_config: dict,
                              system_prompt: Optional[str] = None,
                              tools: Optional[List[Dict]] = None) -> str:
        model = self._get_gemini_model(model_config)

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        if tools:
            gemini_tools = self._convert_tools_to_gemini(tools)
            response = model.generate_content(
                full_prompt,
                tools=gemini_tools
            )

            if response.candidates[0].content.parts[0].function_call:
                return response.candidates[0].content.parts[0]
        else:
            response = model.generate_content(full_prompt)

        return response.text

    def _convert_tools_to_gemini(self, openai_tools: List[Dict]) -> List:
        """将 OpenAI 格式的 tools 转换为 Gemini 格式"""
        gemini_tools = []
        for tool in openai_tools:
            if tool['type'] == 'function':
                func = tool['function']
                gemini_tools.append(
                    genai.protos.Tool(
                        function_declarations=[
                            genai.protos.FunctionDeclaration(
                                name=func['name'],
                                description=func['description'],
                                parameters=func.get('parameters', {})
                            )
                        ]
                    )
                )
        return gemini_tools

ai_client = AIClient()
