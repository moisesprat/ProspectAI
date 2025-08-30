#!/usr/bin/env python3
"""
Technical Analyst Agent - Analyzes technical indicators and generates momentum analysis
"""

import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from agents.base_agent import BaseAgent
from utils.technical_analysis_tool import TechnicalAnalysisTool
from config.config import Config
from crewai import Agent

class TechnicalAnalystAgent(BaseAgent):
    """Technical Analyst Agent that analyzes stock momentum using technical indicators"""
    
    def __init__(self, config_path: str = None):
        super().__init__(
            agent_key="technical_analyst",
            config_path=config_path
        )
        
    
    def create_agent(self) -> Agent:
        """Create and return a CrewAI Agent instance"""
        from crewai import Agent
        
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=self.verbose,
            allow_delegation=self.allow_delegation,
            llm=self._get_llm()
        )
    