import { PlannerOutput, SearchResult } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function postJson<T>(path: string, payload: object): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || `Request failed: ${response.status}`);
    }
    return data as T;
}


export const runPlanner = async (objective: string): Promise<PlannerOutput> => {
    return postJson<PlannerOutput>('/api/research/plan', { objective });
};


export const runSearcher = async (queries: string[]): Promise<SearchResult[]> => {
    const data = await postJson<{ results: SearchResult[] }>('/api/research/search', { queries });
    return data.results;
};

export const runSynthesizer = async (objective: string, searchResults: SearchResult[]): Promise<{ summary: string, sources: { title: string, url: string }[] }> => {
    return postJson<{ summary: string, sources: { title: string, url: string }[] }>('/api/research/synthesize', {
        objective,
        searchResults,
    });
};

export const runPathfinder = async (objective: string, reportSummary: string): Promise<string[]> => {
    const data = await postJson<{ suggestions: string[] }>('/api/research/pathfinder', {
        objective,
        reportSummary,
    });
    return data.suggestions;
};
