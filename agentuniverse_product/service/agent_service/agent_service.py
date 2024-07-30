# !/usr/bin/env python3
# -*- coding:utf-8 -*-

# @Time    : 2024/7/25 21:11
# @Author  : wangchongshi
# @Email   : wangchongshi.wcs@antgroup.com
# @FileName: agent_service.py
from typing import List

from agentuniverse.agent.agent import Agent
from agentuniverse.agent.agent_manager import AgentManager
from agentuniverse.agent.agent_model import AgentModel
from agentuniverse.base.component.component_enum import ComponentEnum
from agentuniverse.llm.llm import LLM
from agentuniverse.llm.llm_manager import LLMManager
from agentuniverse.prompt.prompt import Prompt
from agentuniverse.prompt.prompt_manager import PromptManager
from agentuniverse.prompt.prompt_model import AgentPromptModel
from agentuniverse_product.base.product import Product
from agentuniverse_product.base.product_manager import ProductManager
from agentuniverse_product.base.util.yaml_util import update_nested_yaml_value
from agentuniverse_product.service.model.agent_dto import AgentDTO
from agentuniverse_product.service.model.knowledge_dto import KnowledgeDTO
from agentuniverse_product.service.model.llm_dto import LlmDTO
from agentuniverse_product.service.model.planner_dto import PlannerDTO
from agentuniverse_product.service.model.prompt_dto import PromptDTO
from agentuniverse_product.service.model.tool_dto import ToolDTO
from agentuniverse_product.service.session_service.session_service import SessionService


class AgentService:

    @staticmethod
    def get_agent_list() -> List[AgentDTO]:
        res = []
        product_list: List[Product] = ProductManager().get_instance_obj_list()
        if len(product_list) < 1:
            return res
        for product in product_list:
            if product.type == ComponentEnum.AGENT.value:
                agent_dto = AgentDTO(nickname=product.nickname, avatar=product.avatar, id=product.id)
                agent = product.instance
                agent_model: AgentModel = agent.agent_model
                agent_dto.description = agent_model.info.get('description', '')
                res.append(agent_dto)
        return res

    @staticmethod
    def get_agent_detail(id: str) -> AgentDTO | None:
        product_list: List[Product] = ProductManager().get_instance_obj_list()
        if len(product_list) < 1:
            return None
        for product in product_list:
            if product.type == ComponentEnum.AGENT.value and product.id == id:
                agent_dto = AgentDTO(nickname=product.nickname, avatar=product.avatar, id=product.id,
                                     opening_speech=product.opening_speech)
                agent: Agent = product.instance
                agent_model: AgentModel = agent.agent_model
                agent_dto.description = agent_model.info.get('description', '')
                agent_dto.prompt = AgentService.get_prompt_dto(agent_model)
                agent_dto.llm = AgentService.get_llm_dto(agent_model)
                agent_dto.memory = agent_model.memory.get('name', '')
                agent_dto.tool = AgentService.get_tool_dto_list(agent_model)
                agent_dto.knowledge = AgentService.get_knowledge_dto_list(agent_model)
                agent_dto.planner = AgentService.get_planner_dto(agent_model)
                return agent_dto
        return None

    @staticmethod
    def update_agent(agent_dto: AgentDTO) -> None:
        if agent_dto.id is None:
            raise ValueError("Agent id cannot be None.")
        product: Product = ProductManager().get_instance_obj(agent_dto.id)
        agent: Agent = AgentManager().get_instance_obj(agent_dto.id)
        if product is None or agent is None:
            raise ValueError("The agent or product instance corresponding to the agent id cannot be found.")
        # update agent product yaml configuration file
        AgentService().update_agent_product_config(product, agent_dto, product.component_config_path)
        # update agent yaml configuration file
        AgentService().update_agent_config(agent, agent_dto, agent.component_config_path)

    @staticmethod
    def chat(agent_id: str, session_id: str, params: dict):
        if agent_id is None or session_id is None:
            raise ValueError("Agent id or session id cannot be None.")
        agent: Agent = AgentManager().get_instance_obj(agent_id)
        if agent is None:
            raise ValueError("The agent instance corresponding to the agent id cannot be found.")

    @staticmethod
    def get_planner_dto(agent_model: AgentModel) -> PlannerDTO | None:
        planner = agent_model.plan.get('planner', {})
        planner_name = planner.get('name')
        if planner_name is None:
            return None
        product: Product = ProductManager().get_instance_obj(planner_name)
        return PlannerDTO(nickname=product.nickname if product else '', id=planner_name)

    @staticmethod
    def get_knowledge_dto_list(agent_model: AgentModel) -> List[KnowledgeDTO]:
        knowledge_name_list = agent_model.action.get('knowledge', [])
        res = []
        if len(knowledge_name_list) < 1:
            return res
        for knowledge_name in knowledge_name_list:
            product: Product = ProductManager().get_instance_obj(knowledge_name)
            knowledge_dto = KnowledgeDTO(nickname=product.nickname, id=product.id)
            knowledge = product.instance
            knowledge_dto.description = knowledge.description
            res.append(knowledge_dto)
        return res

    @staticmethod
    def get_tool_dto_list(agent_model: AgentModel) -> List[ToolDTO]:
        tool_name_list = agent_model.action.get('tool', [])
        res = []
        if len(tool_name_list) < 1:
            return res
        for tool_name in tool_name_list:
            product: Product = ProductManager().get_instance_obj(tool_name)
            tool_dto = ToolDTO(nickname=product.nickname, avatar=product.avatar, id=product.id)
            tool = product.instance
            tool_dto.description = tool.description
            res.append(tool_dto)
        return res

    @staticmethod
    def get_prompt_dto(agent_model: AgentModel) -> PromptDTO:
        profile_prompt_model: AgentPromptModel = AgentPromptModel(
            introduction=agent_model.profile.get('introduction'),
            target=agent_model.profile.get('target'),
            instruction=agent_model.profile.get('instruction'))

        prompt_version = agent_model.profile.get('prompt_version')
        version_prompt: Prompt = PromptManager().get_instance_obj(prompt_version)

        if version_prompt is None and not profile_prompt_model:
            raise Exception("Either the `prompt_version` or `introduction & target & instruction`"
                            " in agent profile configuration should be provided.")
        if version_prompt:
            version_prompt_model: AgentPromptModel = AgentPromptModel(
                introduction=getattr(version_prompt, 'introduction', ''),
                target=getattr(version_prompt, 'target', ''),
                instruction=getattr(version_prompt, 'instruction', ''))
            profile_prompt_model = profile_prompt_model + version_prompt_model

        return PromptDTO(introduction=profile_prompt_model.introduction, target=profile_prompt_model.target,
                         instruction=profile_prompt_model.instruction)

    @staticmethod
    def get_llm_dto(agent_model: AgentModel) -> LlmDTO | None:
        llm_model = agent_model.profile.get('llm_model', {})
        llm_id = llm_model.get('name')
        llm: LLM = LLMManager().get_instance_obj(llm_id)
        product: Product = ProductManager().get_instance_obj(llm_id)
        if llm is None:
            return None
        return LlmDTO(id=llm_id, nickname=product.nickname if product else '', temperature=llm.temperature)

    @staticmethod
    def update_agent_product_config(agent_product: Product, agent_dto: AgentDTO, product_config_path: str) -> None:
        if agent_dto is None or agent_dto.opening_speech is None:
            return
        agent_product.opening_speech = agent_dto.opening_speech
        update_nested_yaml_value(product_config_path, {'opening_speech': agent_dto.opening_speech})

    @staticmethod
    def update_agent_config(agent: Agent, agent_dto: AgentDTO, agent_config_path: str) -> None:
        agent_updates = {}
        if agent_dto.description is not None and agent_dto.description != "":
            agent_updates['info.description'] = agent_dto.description
            agent.agent_model.info['description'] = agent_dto.description
        if agent_dto.prompt is not None:
            prompt_dto = agent_dto.prompt
            if prompt_dto.target is not None:
                agent_updates['profile.target'] = agent_dto.prompt.target
                agent.agent_model.profile['target'] = agent_dto.prompt.target
            if prompt_dto.introduction is not None:
                agent_updates['profile.introduction'] = agent_dto.prompt.introduction
                agent.agent_model.profile['introduction'] = agent_dto.prompt.introduction
            if prompt_dto.instruction is not None:
                agent_updates['profile.instruction'] = agent_dto.prompt.instruction
                agent.agent_model.profile['instruction'] = agent_dto.prompt.instruction
        if agent_dto.llm is not None:
            llm_dto = agent_dto.llm
            if llm_dto.id is not None:
                agent_updates['profile.llm_model.name'] = agent_dto.llm.id
                agent.agent_model.profile.get('llm_model')['name'] = agent_dto.llm.id
            if llm_dto.temperature is not None:
                agent_updates['profile.llm_model.temperature'] = agent_dto.llm.temperature
                agent.agent_model.profile.get('llm_model')['temperature'] = agent_dto.llm.temperature
            if llm_dto.model_name is not None:
                agent_updates['profile.llm_model.model_name'] = agent_dto.llm.model_name[0]
                agent.agent_model.profile.get('llm_model')['model_name'] = agent_dto.llm.model_name[0]
        if agent_dto.tool is not None and len(agent_dto.tool) > 0:
            tool_dto_list: List[ToolDTO] = agent_dto.tool
            tool_name_list = [tool_dto.id for tool_dto in tool_dto_list]
            agent_updates['action.tool'] = tool_name_list
            agent.agent_model.action['tool'] = tool_name_list
        if agent_updates:
            update_nested_yaml_value(agent_config_path, agent_updates)
