import React from 'react';
import { AgentName } from './types';
import { PlannerIcon } from './components/icons/PlannerIcon';
import { SearchIcon } from './components/icons/SearchIcon';
import { CrawlerIcon } from './components/icons/CrawlerIcon';
import { AnalyzeIcon } from './components/icons/AnalyzeIcon';
import { FactCheckIcon } from './components/icons/FactCheckIcon';
import { SynthesizerIcon } from './components/icons/SynthesizerIcon';
import { PathfinderIcon } from './components/icons/PathfinderIcon';


export interface AgentInfo {
    name: AgentName;
    description: string;
    icon: React.FC;
}

export const AGENT_INFO: Record<AgentName, AgentInfo> = {
    Pathfinder: {
        name: 'Pathfinder',
        description: 'Analyzes the final report to suggest actionable next steps.',
        icon: PathfinderIcon,
    },
    Planner: {
        name: 'Planner',
        description: 'Analyzes the research objective and creates a step-by-step plan.',
        icon: PlannerIcon,
    },
    Searcher: {
        name: 'Searcher',
        description: 'Executes web searches based on the plan to find relevant sources.',
        icon: SearchIcon,
    },
    Crawler: {
        name: 'Crawler',
        description: 'Fetches and extracts content from the URLs found by the Searcher.',
        icon: CrawlerIcon,
    },
    Analyzer: {
        name: 'Analyzer',
        description: 'Extracts key information and insights from the crawled content.',
        icon: AnalyzeIcon,
    },
    FactChecker: {
        name: 'FactChecker',
        description: 'Verifies the claims identified in the plan against the gathered data.',
        icon: FactCheckIcon,
    },
    Synthesizer: {
        name: 'Synthesizer',
        description: 'Compiles all gathered information into a final, coherent research brief.',
        icon: SynthesizerIcon,
    },
};

export const INITIAL_AGENTS: AgentName[] = [
    'Planner',
    'Searcher',
    'Crawler',
    'Analyzer',
    'FactChecker',
    'Synthesizer',
    'Pathfinder'
];