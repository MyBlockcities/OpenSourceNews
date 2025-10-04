import { GoogleGenAI, Type } from "@google/genai";
import { PlannerOutput, SearchResult } from "../types";

// Fix: Initialize the GoogleGenAI client according to guidelines
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY! });

const plannerSchema = {
    type: Type.OBJECT,
    properties: {
        planRationale: {
            type: Type.STRING,
            description: "A short, high-level summary of the research plan and the reasoning behind the chosen queries and claims."
        },
        queries: {
            type: Type.ARRAY,
            items: { type: Type.STRING },
            description: "A list of 3-5 concise, effective search engine queries to research the user's objective."
        },
        claimsToVerify: {
            type: Type.ARRAY,
            items: { type: Type.STRING },
            description: "A list of 2-4 specific, falsifiable claims that need to be investigated to fulfill the user's objective."
        }
    },
    required: ["planRationale", "queries", "claimsToVerify"]
};


const synthesizerSchema = {
    type: Type.OBJECT,
    properties: {
        summary: {
            type: Type.STRING,
            description: "A detailed, well-structured, and comprehensive summary of the research findings, written in markdown format. It should directly address the user's original objective."
        },
        sources: {
            type: Type.ARRAY,
            items: {
                type: Type.OBJECT,
                properties: {
                    title: { type: Type.STRING },
                    url: { type: Type.STRING }
                },
                required: ["title", "url"]
            },
            description: "A list of all the web sources used to generate the summary, including their titles and URLs."
        }
    },
    required: ["summary", "sources"]
};

const pathfinderSchema = {
    type: Type.OBJECT,
    properties: {
        suggestions: {
            type: Type.ARRAY,
            items: { type: Type.STRING },
            description: "A list of 3-4 distinct, actionable, and insightful next steps or deeper research questions based on the analysis."
        }
    },
    required: ["suggestions"]
}


export const runPlanner = async (objective: string): Promise<PlannerOutput> => {
    const prompt = `
        As a professional AI research planner, your task is to create a comprehensive research plan based on the user's objective.
        
        User Objective: "${objective}"
        
        Based on this objective, please generate:
        1.  A short 'planRationale' explaining your approach.
        2.  A list of 3-5 concise, effective search engine 'queries'.
        3.  A list of 2-4 specific, falsifiable 'claimsToVerify' that are crucial to answering the objective.
        
        Return the response in JSON format according to the provided schema.
    `;

    // Fix: Use ai.models.generateContent with correct parameters
    const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: prompt,
        config: {
            responseMimeType: "application/json",
            responseSchema: plannerSchema,
        },
    });

    // Fix: Use response.text to get the JSON string
    const jsonStr = response.text;
    return JSON.parse(jsonStr) as PlannerOutput;
};


export const runSearcher = async (queries: string[]): Promise<SearchResult[]> => {
    const queryStr = queries.join(", ");
    console.log(`Running searcher with queries: ${queryStr}`);
    
    // Fix: Use ai.models.generateContent with googleSearch tool
    const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: `Based on the following search queries, find the most relevant and authoritative web pages. Queries: ${queryStr}`,
        config: {
            tools: [{ googleSearch: {} }],
        },
    });
    
    const searchResults: SearchResult[] = [];
    // Fix: Use groundingChunks to extract search results
    const groundingChunks = response.candidates?.[0]?.groundingMetadata?.groundingChunks;
    if (groundingChunks) {
        for (const chunk of groundingChunks) {
             if(chunk.web) {
                searchResults.push({
                    url: chunk.web.uri,
                    title: chunk.web.title,
                    snippet: '' // Snippet is not provided by groundingChunks
                });
            }
        }
    }
    
    // We need to deduplicate results as grounding chunks might return the same URL for different queries
    const uniqueResults = searchResults.filter(
      (result, index, self) => index === self.findIndex((r) => r.url === result.url)
    );

    return uniqueResults.slice(0, 5); // Return top 5 unique results
};

export const runSynthesizer = async (objective: string, searchResults: SearchResult[]): Promise<{ summary: string, sources: { title: string, url: string }[] }> => {
    
    const sourcesText = searchResults.map(r => `URL: ${r.url}\nTitle: ${r.title}`).join('\n\n');

    const prompt = `
        As a professional AI research synthesizer, your task is to write a comprehensive research brief based on the provided sources to address the user's objective.

        User Objective: "${objective}"

        Sources:
        ${sourcesText}

        Instructions:
        1.  Carefully review the provided sources.
        2.  Synthesize the information to write a detailed, well-structured, and comprehensive summary that directly answers the user's objective.
        3.  The summary MUST be in markdown format. Use headings, bold text, and lists to structure the information clearly.
        4.  List all the web 'sources' you used to generate the summary, including their titles and URLs.
        5.  Return the response in JSON format according to the provided schema. Do not include any sources that were not used in the summary.
    `;

    // Fix: Use ai.models.generateContent with correct parameters
    const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: prompt,
        config: {
            responseMimeType: "application/json",
            responseSchema: synthesizerSchema,
        },
    });
    
    // Fix: Use response.text to get the JSON string
    const jsonStr = response.text;
    const parsed = JSON.parse(jsonStr);
    return {
        summary: parsed.summary,
        sources: parsed.sources
    };
};

export const runPathfinder = async (objective: string, reportSummary: string): Promise<string[]> => {
    const prompt = `
        As a strategic AI Pathfinder, your role is to identify the most valuable next steps after a research mission is complete.
        
        Initial User Objective: "${objective}"
        
        Generated Report Summary:
        ---
        ${reportSummary}
        ---
        
        Based on the initial objective and the resulting summary, generate a list of 3-4 distinct, actionable next steps. These suggestions should be framed as new research missions. They could be:
        - Deeper dives into a specific sub-topic mentioned in the report.
        - Questions about how to apply the findings.
        - Investigations into adjacent or contrasting topics.
        - Practical actions to take based on the information (e.g., "Draft a business plan for...", "Outline a content strategy for...").
        
        Return the response as a JSON object with a single key "suggestions" containing an array of strings.
    `;

    const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: prompt,
        config: {
            responseMimeType: "application/json",
            responseSchema: pathfinderSchema,
        },
    });

    const jsonStr = response.text;
    const parsed = JSON.parse(jsonStr);
    return parsed.suggestions;
};