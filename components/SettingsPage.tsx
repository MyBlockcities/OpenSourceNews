import React, { useState, useEffect } from 'react';
import { LoadingSpinner } from './icons/LoadingSpinner';
import { apiFetch } from '../services/apiClient';

interface TopicConfig {
    topic_name: string;
    rss_sources?: string[];
    youtube_sources?: string[];
    github_sources?: string[];
    hackernews_sources?: string[];
    x_sources?: string[];
    instagram_sources?: string[];
}

interface FeedsConfig {
    topics: TopicConfig[];
}

const SOURCE_TYPES = [
    { key: 'rss_sources', label: 'RSS Feeds', placeholder: 'https://example.com/feed/' },
    { key: 'youtube_sources', label: 'YouTube', placeholder: '@ChannelName or channel ID' },
    { key: 'hackernews_sources', label: 'Hacker News', placeholder: 'search keyword' },
    { key: 'github_sources', label: 'GitHub Trending', placeholder: 'language (e.g. python)' },
    { key: 'x_sources', label: 'X / Twitter', placeholder: 'username (without @)' },
] as const;

const SettingsPage: React.FC = () => {
    const [config, setConfig] = useState<FeedsConfig | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saveStatus, setSaveStatus] = useState<string>('');
    const [editingTopic, setEditingTopic] = useState<number | null>(null);
    const [newSourceValue, setNewSourceValue] = useState<Record<string, string>>({});
    const [newTopicName, setNewTopicName] = useState('');
    const [showAddTopic, setShowAddTopic] = useState(false);

    useEffect(() => {
        loadConfig();
    }, []);

    const loadConfig = async () => {
        try {
            setLoading(true);
            const resp = await apiFetch('/api/config/feeds');
            if (resp.ok) {
                const data = await resp.json();
                setConfig(data);
            } else {
                console.error('Failed to load config');
            }
        } catch (error) {
            console.error('Error loading config:', error);
        } finally {
            setLoading(false);
        }
    };

    const saveConfig = async () => {
        if (!config) return;
        try {
            setSaving(true);
            setSaveStatus('');
            const resp = await apiFetch('/api/config/feeds', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });
            if (resp.ok) {
                setSaveStatus('Saved successfully');
                setTimeout(() => setSaveStatus(''), 3000);
            } else {
                const data = await resp.json();
                setSaveStatus(`Error: ${data.error}`);
            }
        } catch (error) {
            setSaveStatus(`Error: ${error}`);
        } finally {
            setSaving(false);
        }
    };

    const addSource = (topicIdx: number, sourceType: string) => {
        const key = `${topicIdx}-${sourceType}`;
        const value = newSourceValue[key]?.trim();
        if (!value || !config) return;

        const updated = { ...config };
        const topic = { ...updated.topics[topicIdx] };
        const sources = [...(topic[sourceType as keyof TopicConfig] as string[] || [])];
        if (!sources.includes(value)) {
            sources.push(value);
        }
        (topic as any)[sourceType] = sources;
        updated.topics[topicIdx] = topic;
        setConfig(updated);
        setNewSourceValue(prev => ({ ...prev, [key]: '' }));
    };

    const removeSource = (topicIdx: number, sourceType: string, sourceIdx: number) => {
        if (!config) return;
        const updated = { ...config };
        const topic = { ...updated.topics[topicIdx] };
        const sources = [...(topic[sourceType as keyof TopicConfig] as string[] || [])];
        sources.splice(sourceIdx, 1);
        (topic as any)[sourceType] = sources;
        updated.topics[topicIdx] = topic;
        setConfig(updated);
    };

    const removeTopic = (topicIdx: number) => {
        if (!config) return;
        if (!confirm(`Remove topic "${config.topics[topicIdx].topic_name}"?`)) return;
        const updated = { ...config };
        updated.topics = updated.topics.filter((_, i) => i !== topicIdx);
        setConfig(updated);
        setEditingTopic(null);
    };

    const addTopic = () => {
        if (!newTopicName.trim() || !config) return;
        const updated = { ...config };
        updated.topics = [...updated.topics, {
            topic_name: newTopicName.trim(),
            rss_sources: [],
            youtube_sources: [],
            hackernews_sources: [],
            github_sources: [],
            x_sources: [],
        }];
        setConfig(updated);
        setNewTopicName('');
        setShowAddTopic(false);
        setEditingTopic(updated.topics.length - 1);
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <LoadingSpinner className="w-8 h-8" />
                <span className="ml-3 text-gray-400">Loading configuration...</span>
            </div>
        );
    }

    if (!config) {
        return (
            <div className="bg-gray-800/30 rounded-lg p-8 text-center border border-gray-700">
                <p className="text-gray-400">Failed to load configuration.</p>
                <p className="text-gray-500 text-sm mt-2">Make sure the API server is running.</p>
            </div>
        );
    }

    return (
        <div className="animate-fade-in">
            <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-green-400 font-space-mono mb-2">
                    Settings
                </h2>
                <p className="text-gray-400">Configure news sources and topic buckets</p>
            </div>

            {/* Save bar */}
            <div className="bg-gray-800/30 rounded-lg p-4 mb-6 border border-gray-700 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <span className="text-gray-400 text-sm">{config.topics.length} topic buckets configured</span>
                    {saveStatus && (
                        <span className={`text-sm ${saveStatus.startsWith('Error') ? 'text-red-400' : 'text-green-400'}`}>
                            {saveStatus}
                        </span>
                    )}
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => setShowAddTopic(true)}
                        className="bg-gray-700 hover:bg-gray-600 text-white text-sm font-semibold px-4 py-2 rounded-md transition-colors"
                    >
                        + Add Topic
                    </button>
                    <button
                        onClick={saveConfig}
                        disabled={saving}
                        className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-600 text-white font-semibold px-6 py-2 rounded-md transition-colors flex items-center gap-2"
                    >
                        {saving ? <><LoadingSpinner className="w-4 h-4" /> Saving...</> : 'Save Changes'}
                    </button>
                </div>
            </div>

            {/* Add Topic Modal */}
            {showAddTopic && (
                <div className="bg-gray-800/50 rounded-lg p-4 mb-6 border border-cyan-500 flex gap-2">
                    <input
                        type="text"
                        value={newTopicName}
                        onChange={e => setNewTopicName(e.target.value)}
                        placeholder="New topic name (e.g. Robotics & Hardware)"
                        className="bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-gray-200 text-sm flex-grow"
                        onKeyDown={e => e.key === 'Enter' && addTopic()}
                        autoFocus
                    />
                    <button onClick={addTopic} className="bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-semibold px-4 py-2 rounded-md">Add</button>
                    <button onClick={() => setShowAddTopic(false)} className="bg-gray-700 hover:bg-gray-600 text-white text-sm px-4 py-2 rounded-md">Cancel</button>
                </div>
            )}

            {/* Topic Cards */}
            <div className="space-y-4">
                {config.topics.map((topic, topicIdx) => {
                    const isExpanded = editingTopic === topicIdx;
                    const totalSources = SOURCE_TYPES.reduce(
                        (sum, st) => sum + ((topic[st.key as keyof TopicConfig] as string[]) || []).length, 0
                    );

                    return (
                        <div key={topicIdx} className="bg-gray-800/30 rounded-lg border border-gray-700 overflow-hidden">
                            {/* Topic header */}
                            <div
                                className="p-4 flex items-center justify-between cursor-pointer hover:bg-gray-800/50 transition-colors"
                                onClick={() => setEditingTopic(isExpanded ? null : topicIdx)}
                            >
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-200">{topic.topic_name}</h3>
                                    <p className="text-sm text-gray-500">{totalSources} sources configured</p>
                                </div>
                                <div className="flex items-center gap-3">
                                    <div className="flex gap-1">
                                        {SOURCE_TYPES.map(st => {
                                            const count = ((topic[st.key as keyof TopicConfig] as string[]) || []).length;
                                            return count > 0 ? (
                                                <span key={st.key} className="bg-gray-700 text-gray-400 text-xs px-2 py-0.5 rounded">
                                                    {st.label}: {count}
                                                </span>
                                            ) : null;
                                        })}
                                    </div>
                                    <span className="text-gray-500 text-lg">{isExpanded ? '-' : '+'}</span>
                                </div>
                            </div>

                            {/* Expanded source editor */}
                            {isExpanded && (
                                <div className="border-t border-gray-700 p-4 space-y-4">
                                    {SOURCE_TYPES.map(st => {
                                        const sources = (topic[st.key as keyof TopicConfig] as string[]) || [];
                                        const inputKey = `${topicIdx}-${st.key}`;

                                        return (
                                            <div key={st.key}>
                                                <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase">
                                                    {st.label} ({sources.length})
                                                </label>

                                                {/* Existing sources */}
                                                {sources.length > 0 && (
                                                    <div className="flex flex-wrap gap-1 mb-2">
                                                        {sources.map((src, srcIdx) => (
                                                            <span
                                                                key={srcIdx}
                                                                className="bg-gray-700 text-gray-300 text-xs px-2 py-1 rounded flex items-center gap-1 group"
                                                            >
                                                                <span className="max-w-[300px] truncate">{src}</span>
                                                                <button
                                                                    onClick={() => removeSource(topicIdx, st.key, srcIdx)}
                                                                    className="text-gray-500 hover:text-red-400 transition-colors ml-1"
                                                                    title="Remove"
                                                                >
                                                                    x
                                                                </button>
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}

                                                {/* Add new source */}
                                                <div className="flex gap-2">
                                                    <input
                                                        type="text"
                                                        value={newSourceValue[inputKey] || ''}
                                                        onChange={e => setNewSourceValue(prev => ({ ...prev, [inputKey]: e.target.value }))}
                                                        placeholder={st.placeholder}
                                                        className="bg-gray-900 border border-gray-600 rounded-md px-3 py-1.5 text-gray-200 text-sm flex-grow"
                                                        onKeyDown={e => e.key === 'Enter' && addSource(topicIdx, st.key)}
                                                    />
                                                    <button
                                                        onClick={() => addSource(topicIdx, st.key)}
                                                        className="bg-gray-700 hover:bg-gray-600 text-white text-xs font-semibold px-3 py-1.5 rounded-md transition-colors"
                                                    >
                                                        Add
                                                    </button>
                                                </div>
                                            </div>
                                        );
                                    })}

                                    <div className="pt-3 border-t border-gray-700 flex justify-end">
                                        <button
                                            onClick={() => removeTopic(topicIdx)}
                                            className="text-red-400 hover:text-red-300 text-sm font-semibold transition-colors"
                                        >
                                            Remove Topic
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Info */}
            <div className="bg-gray-800/20 rounded-lg p-4 border border-gray-700/50 mt-6">
                <h4 className="text-sm font-semibold text-gray-400 mb-2">How It Works</h4>
                <ul className="text-sm text-gray-500 space-y-1">
                    <li>- Changes are saved to <code className="text-gray-400">config/feeds.yaml</code></li>
                    <li>- The daily pipeline reads this config at 07:00 UTC every day</li>
                    <li>- Each topic bucket collects from all its configured sources</li>
                    <li>- Items are classified with the configured LLM when one is available, otherwise fallback metadata is used</li>
                    <li>- X/Twitter sources are placeholders until the official API is implemented</li>
                </ul>
            </div>
        </div>
    );
};

export default SettingsPage;
