import React, { useState, useEffect } from 'react';
import { PlannerOutput } from '../types';
import { PlusIcon } from './icons/PlusIcon';
import { TrashIcon } from './icons/TrashIcon';
import { LoadingSpinner } from './icons/LoadingSpinner';

interface PlanEditorProps {
    initialPlan: PlannerOutput;
    onConfirm: (plan: PlannerOutput) => void;
    onCancel: () => void;
}

const PlanEditor: React.FC<PlanEditorProps> = ({ initialPlan, onConfirm, onCancel }) => {
    const [queries, setQueries] = useState<string[]>([]);
    const [claims, setClaims] = useState<string[]>([]);
    // Fix: Manage loading state locally to show loading indicator correctly on confirm.
    const [isContinuing, setIsContinuing] = useState(false);

    useEffect(() => {
        setQueries(initialPlan.queries);
        setClaims(initialPlan.claimsToVerify);
    }, [initialPlan]);

    const handleQueryChange = (index: number, value: string) => {
        const newQueries = [...queries];
        newQueries[index] = value;
        setQueries(newQueries);
    };

    const addQuery = () => setQueries([...queries, '']);
    const removeQuery = (index: number) => setQueries(queries.filter((_, i) => i !== index));

    const handleClaimChange = (index: number, value: string) => {
        const newClaims = [...claims];
        newClaims[index] = value;
        setClaims(newClaims);
    };

    const addClaim = () => setClaims([...claims, '']);
    const removeClaim = (index: number) => setClaims(claims.filter((_, i) => i !== index));
    
    const handleConfirm = () => {
        setIsContinuing(true);
        const confirmedPlan: PlannerOutput = {
            ...initialPlan,
            queries: queries.filter(q => q.trim() !== ''),
            claimsToVerify: claims.filter(c => c.trim() !== ''),
        };
        onConfirm(confirmedPlan);
    }

    return (
        <div className="bg-gray-800/50 rounded-lg p-6 shadow-2xl shadow-yellow-500/10 border border-yellow-700 mb-8 animate-fade-in">
            <h2 className="text-2xl font-bold mb-1 text-yellow-300 font-space-mono">Step 1: Review & Confirm Research Plan</h2>
            <p className="text-gray-400 mb-6">The Planner agent has created a starting point. You can modify the search queries and claims to verify before continuing.</p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Queries */}
                <div>
                    <h3 className="text-lg font-semibold text-gray-200 mb-3">Search Queries to Execute</h3>
                    <div className="space-y-3">
                        {queries.map((query, index) => (
                            <div key={index} className="flex items-center gap-2">
                                <input
                                    type="text"
                                    value={query}
                                    onChange={(e) => handleQueryChange(index, e.target.value)}
                                    className="flex-grow bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-gray-200 focus:ring-1 focus:ring-cyan-500 focus:outline-none"
                                />
                                <button onClick={() => removeQuery(index)} className="p-2 text-gray-500 hover:text-red-400"><TrashIcon className="w-5 h-5" /></button>
                            </div>
                        ))}
                        <button onClick={addQuery} className="flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 font-semibold">
                            <PlusIcon className="w-4 h-4" /> Add Query
                        </button>
                    </div>
                </div>

                {/* Claims to Verify */}
                <div>
                    <h3 className="text-lg font-semibold text-gray-200 mb-3">Key Claims to Verify</h3>
                    <div className="space-y-3">
                         {claims.map((claim, index) => (
                            <div key={index} className="flex items-center gap-2">
                                <input
                                    type="text"
                                    value={claim}
                                    onChange={(e) => handleClaimChange(index, e.target.value)}
                                    className="flex-grow bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-gray-200 focus:ring-1 focus:ring-cyan-500 focus:outline-none"
                                />
                                <button onClick={() => removeClaim(index)} className="p-2 text-gray-500 hover:text-red-400"><TrashIcon className="w-5 h-5" /></button>
                            </div>
                        ))}
                        <button onClick={addClaim} className="flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 font-semibold">
                            <PlusIcon className="w-4 h-4" /> Add Claim
                        </button>
                    </div>
                </div>
            </div>
            
            <div className="mt-8 pt-6 border-t border-gray-700 flex flex-col sm:flex-row justify-end items-center gap-4">
                 <button
                    onClick={onCancel}
                    disabled={isContinuing}
                    className="text-gray-400 hover:text-white font-semibold px-6 py-2 rounded-md transition duration-200 disabled:opacity-50"
                >
                    Cancel Mission
                </button>
                <button
                    onClick={handleConfirm}
                    disabled={isContinuing}
                    className="bg-green-600 text-white font-semibold px-6 py-3 rounded-md hover:bg-green-500 disabled:bg-gray-600 disabled:cursor-not-allowed transition duration-200 flex items-center justify-center gap-2 min-w-[220px]"
                >
                    {isContinuing ? (
                        <>
                            <LoadingSpinner />
                            <span>Continuing Mission...</span>
                        </>
                    ) : 'Confirm Plan & Continue Mission'}
                </button>
            </div>
        </div>
    );
};

export default PlanEditor;
