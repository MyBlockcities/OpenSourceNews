import React from 'react';
import { FinalReport } from '../types';

// A simple markdown-to-html renderer
const MarkdownRenderer: React.FC<{ content: string }> = ({ content }) => {
    // Correctly process list items first, then other elements
    const processList = (text: string): string => {
        const lines = text.split('\n');
        let html = '';
        let inList = false;
        for (const line of lines) {
            const trimmedLine = line.trim();
            if (trimmedLine.startsWith('* ') || trimmedLine.startsWith('- ')) {
                if (!inList) {
                    html += '<ul>';
                    inList = true;
                }
                html += `<li class="ml-6">${trimmedLine.substring(2)}</li>`;
            } else {
                if (inList) {
                    html += '</ul>';
                    inList = false;
                }
                html += line + '\n';
            }
        }
        if (inList) {
            html += '</ul>';
        }
        return html;
    };
    
    let htmlContent = processList(content);

    htmlContent = htmlContent
        .replace(/^## (.*$)/gim, '<h3 class="text-xl font-bold mt-6 mb-2 text-gray-200">$1</h3>')
        .replace(/^### (.*$)/gim, '<h4 class="text-lg font-semibold mt-4 mb-1 text-gray-300">$1</h4>')
        .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-gray-200">$1</strong>')
        .split('\n').map(p => {
             // Avoid wrapping ul/li in p tags
            if (p.trim().startsWith('<ul>') || p.trim().startsWith('</ul>')) return p;
            return p.trim() ? `<p class="mb-4 text-gray-300 leading-relaxed">${p}</p>` : '';
        }).join('')
        .replace(/<p class="mb-4 text-gray-300 leading-relaxed">(<ul>.*?<\/ul])<\/p>/g, '$1')
        .replace(/<p class="mb-4 text-gray-300 leading-relaxed"><h[34]>/g, '<h')
        .replace(/<\/h[34]><\/p>/g, '</h' + '3>');


    return <div dangerouslySetInnerHTML={{ __html: htmlContent }} />;
};

interface ResultsDisplayProps {
    report: FinalReport;
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({ report }) => {
    return (
        <div className="bg-gray-800/50 rounded-lg p-6 shadow-2xl shadow-green-500/10 border border-gray-700">
            <h2 className="text-3xl font-bold mb-6 text-green-400 font-space-mono border-b border-gray-600 pb-3">Final Research Brief</h2>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2">
                    <div className="prose prose-invert max-w-none">
                       <MarkdownRenderer content={report.summary} />
                    </div>
                </div>

                <div className="lg:col-span-1">
                    <h3 className="text-xl font-bold mb-4 text-gray-200">Cited Sources</h3>
                    <div className="space-y-3">
                        {report.sources.map((source, index) => (
                            <div key={index} className="bg-gray-900/70 p-3 rounded-md border border-gray-700">
                                <a 
                                    href={source.url} 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="text-cyan-400 hover:underline font-semibold"
                                >
                                    {source.title}
                                </a>
                                <p className="text-xs text-gray-500 mt-1 break-all">{source.url}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ResultsDisplay;
