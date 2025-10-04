export type AgentName = 'Planner' | 'Searcher' | 'Crawler' | 'Analyzer' | 'FactChecker' | 'Synthesizer' | 'Pathfinder';

export type AgentStatus = 'pending' | 'in-progress' | 'completed' | 'error';

export interface AgentState {
    name: AgentName;
    status: AgentStatus;
    logs: string[];
    details?: any; // To store agent-specific output
}

export interface PlannerOutput {
    planRationale: string;
    queries: string[];
    claimsToVerify: string[];
}

export interface SearchResult {
    url: string;
    title: string;
    snippet: string;
}

export interface SearcherOutput {
    results: SearchResult[];
}

export interface FactCheckResult {
    claim: string;
    verification: string;
    sources: string[];
}

export interface SynthesizerOutput {
    report: string;
    sources: { title: string, url: string }[];
}


export interface FinalReport {
    summary: string;
    sources: { title: string, url: string }[];
}

export interface MissionState {
    objective: string;
    agents: AgentState[];
    status: 'idle' | 'running' | 'editing-plan' | 'completed' | 'error';
    plan?: PlannerOutput;
    finalReport?: FinalReport;
    error?: string;
    suggestions?: string[];
}