import React from 'react';
import { LightbulbIcon } from './icons/LightbulbIcon';

interface SuggestionsBoxProps {
    onSuggestionClick: (suggestion: string) => void;
}

const suggestions = [
    "What are the latest advancements in AI-driven drug discovery?",
    "Compare the economic impacts of renewable vs. traditional energy sources.",
    "Investigate the role of gut microbiome in mental health.",
    "What is the future of decentralized finance (DeFi)?",
];

const SuggestionsBox: React.FC<SuggestionsBoxProps> = ({ onSuggestionClick }) => {
    return (
        <div className="bg-gray-800/30 rounded-lg p-6 animate-fade-in">
            <div className="flex items-center gap-3 mb-4">
                <LightbulbIcon />
                <h2 className="text-xl font-semibold text-gray-200">Start a new mission</h2>
            </div>
            <p className="text-gray-400 mb-5">Or try one of these examples:</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {suggestions.map((s) => (
                    <button
                        key={s}
                        onClick={() => onSuggestionClick(s)}
                        className="text-left p-3 bg-gray-700/50 rounded-md hover:bg-gray-700 transition duration-200 text-gray-300 text-sm"
                    >
                        {s}
                    </button>
                ))}
            </div>
        </div>
    );
};

export default SuggestionsBox;
