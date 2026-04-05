import React, { useState, useCallback, useRef } from 'react';
import { AgentState, FinalReport, MissionState, PlannerOutput, SearchResult } from './types';
import { INITIAL_AGENTS } from './constants';
import * as geminiService from './services/geminiService';

import AgentCard from './components/AgentCard';
import PlanEditor from './components/PlanEditor';
import ResultsDisplay from './components/ResultsDisplay';
import SuggestionsBox from './components/SuggestionsBox';
import { PathfinderIcon } from './components/icons/PathfinderIcon';
import PathfinderResults from './components/PathfinderResults';
import AutomationHub from './components/AutomationHub';
import DailyFeedViewer from './components/DailyFeedViewer';
import NewsFeed from './components/NewsFeed';
import SettingsPage from './components/SettingsPage';

type ViewMode = 'news' | 'mission' | 'feed' | 'automation' | 'settings';

const App: React.FC = () => {
    const [missionState, setMissionState] = useState<MissionState>({
        objective: '',
        agents: [],
        status: 'idle',
    });
    const [inputValue, setInputValue] = useState('');
    const [viewMode, setViewMode] = useState<ViewMode>('news');
    
    const missionStateRef = useRef(missionState);
    missionStateRef.current = missionState;

    const resetMission = () => {
        setMissionState({
            objective: '',
            agents: [],
            status: 'idle',
        });
        setInputValue('');
    };
    
    const updateAgentState = useCallback((agentName: AgentState['name'], newProps: Partial<AgentState>) => {
        setMissionState(prevState => ({
            ...prevState,
            agents: prevState.agents.map(agent =>
                agent.name === agentName ? { ...agent, ...newProps } : agent
            ),
        }));
    }, []);

    const startMission = async (objective: string) => {
        setMissionState({
            objective,
            status: 'running',
            agents: INITIAL_AGENTS.map(name => ({ name, status: 'pending', logs: [] })),
        });

        try {
            updateAgentState('Planner', { status: 'in-progress', logs: ['Generating research plan...'] });
            const plan = await geminiService.runPlanner(objective);
            updateAgentState('Planner', { status: 'completed', logs: ['Plan generated.', `Rationale: ${plan.planRationale}`, `Queries: ${plan.queries.join(', ')}`, `Claims: ${plan.claimsToVerify.join(', ')}`], details: plan });
            setMissionState(prev => ({ ...prev, status: 'editing-plan', plan }));

        } catch (error) {
            console.error("Error during planning phase:", error);
            const errorMessage = error instanceof Error ? error.message : "An unknown error occurred.";
            updateAgentState('Planner', { status: 'error', logs: [...(missionStateRef.current.agents.find(a => a.name === 'Planner')?.logs || []), `Error: ${errorMessage}`] });
            setMissionState(prev => ({...prev, status: 'error', error: `Failed during planning: ${errorMessage}`}));
        }
    };

    const continueMission = async (confirmedPlan: PlannerOutput) => {
        setMissionState(prev => ({ ...prev, status: 'running', plan: confirmedPlan }));

        try {
            // Searcher
            updateAgentState('Searcher', { status: 'in-progress', logs: [`Executing searches for: ${confirmedPlan.queries.join(', ')}`] });
            const searchResults: SearchResult[] = await geminiService.runSearcher(confirmedPlan.queries);
            if (!searchResults || searchResults.length === 0) throw new Error("Searcher returned no results.");
            const searchLogs = [`Found ${searchResults.length} relevant sources.`, ...searchResults.map(r => `- ${r.title} (${r.url})`)];
            updateAgentState('Searcher', { status: 'completed', logs: searchLogs, details: { results: searchResults } });
            
            // Skipped agents for demo simplicity
            updateAgentState('Crawler', { status: 'completed', logs: ['Content extraction skipped for this simplified demo.']});
            updateAgentState('Analyzer', { status: 'completed', logs: ['Analysis skipped for this simplified demo.']});
            updateAgentState('FactChecker', { status: 'completed', logs: ['Fact-checking skipped for this simplified demo.']});

            // Synthesizer
            updateAgentState('Synthesizer', { status: 'in-progress', logs: ['Synthesizing information into a final report...'] });
            const finalReportData = await geminiService.runSynthesizer(missionStateRef.current.objective, searchResults);
            const finalReport: FinalReport = { summary: finalReportData.summary, sources: finalReportData.sources };
            updateAgentState('Synthesizer', { status: 'completed', logs: ['Final report generated successfully.'], details: finalReport });
            setMissionState(prev => ({ ...prev, finalReport }));

            // Pathfinder
            updateAgentState('Pathfinder', { status: 'in-progress', logs: ['Analyzing report for next steps...'] });
            const suggestions = await geminiService.runPathfinder(missionStateRef.current.objective, finalReport.summary);
            updateAgentState('Pathfinder', { status: 'completed', logs: [`Generated ${suggestions.length} suggestions.`], details: { suggestions } });
            
            setMissionState(prev => ({ ...prev, status: 'completed', suggestions }));

        } catch (error) {
            console.error("Error during mission execution:", error);
            const errorMessage = error instanceof Error ? error.message : "An unknown error occurred.";
            const runningAgent = missionStateRef.current.agents.find(a => a.status === 'in-progress');
            if (runningAgent) {
                updateAgentState(runningAgent.name, { status: 'error', logs: [...(runningAgent.logs || []), `Error: ${errorMessage}`] });
            }
            setMissionState(prev => ({...prev, status: 'error', error: `Mission failed: ${errorMessage}`}));
        }
    }
    
    const handleFormSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (inputValue.trim()) {
            startMission(inputValue.trim());
        }
    };
    
    const handleSuggestionClick = (suggestion: string) => {
        setInputValue(suggestion);
        setTimeout(() => {
            startMission(suggestion);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }, 100);
    }
    
    const isMissionActive = missionState.status !== 'idle';
    
    return (
        <div className="bg-gray-900 min-h-screen text-white font-sans">
            <div className="container mx-auto px-4 py-8 md:py-12">
                <header className="text-center mb-10">
                    <div className="inline-flex items-center gap-4 mb-2">
                        <PathfinderIcon />
                        <h1 className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-green-400 font-space-mono">
                            Open Source News
                        </h1>
                    </div>
                    <p className="text-gray-400 text-lg">Aggregated intelligence from across the open source ecosystem.</p>
                    <div className="mt-6 flex justify-center bg-gray-800/50 p-1 rounded-lg max-w-3xl mx-auto border border-gray-700">
                        {([
                            ['news', 'News Feed'],
                            ['feed', 'Daily Reports'],
                            ['mission', 'Research'],
                            ['automation', 'Automation'],
                            ['settings', 'Settings'],
                        ] as [ViewMode, string][]).map(([mode, label]) => (
                            <button
                                key={mode}
                                onClick={() => setViewMode(mode)}
                                className={`flex-1 py-2 rounded-md transition-colors duration-200 font-semibold text-sm ${viewMode === mode ? 'bg-cyan-600 text-white' : 'text-gray-300 hover:bg-gray-700'}`}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </header>

                <main className="max-w-4xl mx-auto">
                    {viewMode === 'news' ? (
                        <NewsFeed />
                    ) : viewMode === 'settings' ? (
                        <SettingsPage />
                    ) : viewMode === 'mission' ? (
                        <>
                            {!isMissionActive && (
                                <div className="mb-8">
                                    <form id="mission-form" onSubmit={handleFormSubmit} className="flex flex-col sm:flex-row gap-2 mb-6">
                                        <input
                                            type="text"
                                            value={inputValue}
                                            onChange={(e) => setInputValue(e.target.value)}
                                            placeholder="Enter your research objective..."
                                            className="flex-grow bg-gray-800 border-2 border-gray-700 rounded-md px-4 py-3 text-lg text-gray-200 focus:ring-2 focus:ring-cyan-500 focus:outline-none transition"
                                        />
                                        <button
                                            type="submit"
                                            disabled={!inputValue.trim()}
                                            className="bg-cyan-600 text-white font-semibold px-6 py-3 rounded-md hover:bg-cyan-500 disabled:bg-gray-600 disabled:cursor-not-allowed transition duration-200"
                                        >
                                            Start Mission
                                        </button>
                                    </form>
                                <SuggestionsBox onSuggestionClick={handleSuggestionClick} />
                                </div>
                            )}
                            
                            {isMissionActive && (
                                <div className="bg-gray-800/30 rounded-lg p-6 mb-8 border border-gray-700">
                                    <h2 className="text-sm font-semibold text-gray-400 mb-2">MISSION OBJECTIVE</h2>
                                    <p className="text-xl text-gray-200">{missionState.objective}</p>
                                </div>
                            )}

                            {missionState.status === 'editing-plan' && missionState.plan && (
                                <PlanEditor
                                    initialPlan={missionState.plan}
                                    onConfirm={continueMission}
                                    onCancel={resetMission}
                                />
                            )}

                            {missionState.agents.length > 0 && (
                                <div className="space-y-4 mb-8">
                                    {missionState.agents.map((agent) => (
                                        <AgentCard key={agent.name} agentState={agent} />
                                    ))}
                                </div>
                            )}

                            {missionState.status === 'completed' && missionState.finalReport && (
                                <>
                                    <ResultsDisplay report={missionState.finalReport} />
                                    {missionState.suggestions && missionState.suggestions.length > 0 && (
                                        <PathfinderResults suggestions={missionState.suggestions} onSuggestionClick={handleSuggestionClick} />
                                    )}
                                    <div className="text-center mt-8">
                                        <button onClick={resetMission} className="bg-cyan-600 text-white font-semibold px-8 py-3 rounded-md hover:bg-cyan-500 transition duration-200">
                                            Start New Mission
                                        </button>
                                    </div>
                                </>
                            )}

                            {missionState.status === 'error' && (
                                <div className="bg-red-900/50 border border-red-700 text-red-200 p-4 rounded-lg text-center">
                                    <h3 className="font-bold text-lg mb-2">Mission Failed</h3>
                                    <p>{missionState.error}</p>
                                    <button onClick={resetMission} className="mt-4 bg-red-700 hover:bg-red-600 text-white font-semibold px-4 py-2 rounded-md">
                                        Try Again
                                    </button>
                                </div>
                            )}
                        </>
                    ) : viewMode === 'feed' ? (
                        <DailyFeedViewer />
                    ) : (
                        <AutomationHub />
                    )}
                </main>
            </div>
        </div>
    );
};

export default App;