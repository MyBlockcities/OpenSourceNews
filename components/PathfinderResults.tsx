import React from 'react';
import { LightbulbIcon } from './icons/LightbulbIcon';

interface PathfinderResultsProps {
    suggestions: string[];
    onSuggestionClick: (suggestion: string) => void;
}

const PathfinderResults: React.FC<PathfinderResultsProps> = ({ suggestions, onSuggestionClick }) => {
    return (
        <div className="bg-gray-800/50 rounded-lg p-6 mt-8 border border-cyan-700 animate-fade-in">
            <div className="flex items-center gap-3 mb-4">
                <LightbulbIcon />
                <h2 className="text-2xl font-bold text-cyan-300 font-space-mono">Suggested Next Steps</h2>
            </div>
            <p className="text-gray-400 mb-5">The Pathfinder agent has analyzed the report and suggests the following actions or deeper investigations. Click one to start a new mission.</p>
            <div className="flex flex-col gap-3">
                {suggestions.map((s) => (
                    <button
                        key={s}
                        onClick={() => onSuggestionClick(s)}
                        className="text-left p-4 bg-gray-700/50 rounded-md hover:bg-gray-700 hover:border-cyan-500 border border-transparent transition duration-200 text-gray-200"
                    >
                        {s}
                    </button>
                ))}
            </div>
        </div>
    );
};

export default PathfinderResults;