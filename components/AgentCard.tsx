import React, { useState } from 'react';
import { AgentState } from '../types';
import { AGENT_INFO } from '../constants';
import { LoadingSpinner } from './icons/LoadingSpinner';
import { ChevronDownIcon } from './icons/ChevronDownIcon';

const StatusIndicator: React.FC<{ status: AgentState['status'] }> = ({ status }) => {
    switch (status) {
        case 'pending':
            return <div className="h-4 w-4 rounded-full bg-gray-500" title="Pending"></div>;
        case 'in-progress':
            return <LoadingSpinner />;
        case 'completed':
            return <div className="h-4 w-4 rounded-full bg-green-500" title="Completed"></div>;
        case 'error':
            return <div className="h-4 w-4 rounded-full bg-red-500" title="Error"></div>;
        default:
            return null;
    }
};

interface AgentCardProps {
    agentState: AgentState;
}

const AgentCard: React.FC<AgentCardProps> = ({ agentState }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const agentInfo = AGENT_INFO[agentState.name];

    if (!agentInfo) {
        return <div>Error: Agent info not found for {agentState.name}</div>;
    }
    
    const hasLogs = agentState.logs && agentState.logs.length > 0;

    return (
        <div className={`bg-gray-800/50 rounded-lg p-4 shadow-lg border border-gray-700 transition-all duration-300 ${agentState.status === 'in-progress' ? 'animate-pulse-strong border-cyan-500' : ''}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className="text-cyan-400">
                        <agentInfo.icon />
                    </div>
                    <div>
                        <h3 className="text-lg font-bold text-gray-200">{agentInfo.name}</h3>
                        <p className="text-sm text-gray-400">{agentInfo.description}</p>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                   <StatusIndicator status={agentState.status} />
                   {(hasLogs || agentState.details) && (
                       <button onClick={() => setIsExpanded(!isExpanded)} className="text-gray-400 hover:text-white">
                           <ChevronDownIcon className={`w-5 h-5 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
                       </button>
                   )}
                </div>
            </div>
            {isExpanded && (
                 <div className="mt-4 pt-4 border-t border-gray-600">
                    {hasLogs && (
                        <pre className="text-xs text-gray-300 bg-gray-900/50 p-3 rounded-md max-h-40 overflow-y-auto font-mono whitespace-pre-wrap">
                            {agentState.logs.join('\n')}
                        </pre>
                    )}
                    {agentState.name === 'Pathfinder' && agentState.details?.suggestions && (
                         <div className="mt-3 bg-gray-900/50 p-3 rounded-md">
                            <h4 className="font-semibold text-gray-300 text-sm mb-2">Generated Next Steps:</h4>
                            <ul className="list-disc list-inside space-y-2 text-sm text-gray-300">
                                {agentState.details.suggestions.map((s: string, i: number) => <li key={i}>{s}</li>)}
                            </ul>
                        </div>
                    )}
                 </div>
            )}
        </div>
    );
};

export default AgentCard;