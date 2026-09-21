"use client";

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { 
  Database, Settings, Send, Bot, User, DatabaseZap, Loader2, 
  Trash2, PlusCircle, Activity
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

// Constants
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  agent?: string;
  timestamp: Date;
}

interface Connection {
  id: string;
  name: string;
  connection_string: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hello! I am your AI Data Analyst Platform. Please configure your PostgreSQL connection and ask me anything about your data.",
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  
  // Connections state
  const [connections, setConnections] = useState<Connection[]>([]);
  const [activeConnectionId, setActiveConnectionId] = useState<string>("");
  const [isConnDialogOpen, setIsConnDialogOpen] = useState(false);
  const [newConnName, setNewConnName] = useState("");
  const [newConnString, setNewConnString] = useState("");
  const [isTestMode, setIsTestMode] = useState(true); // Toggle to skip API for UI testing
  
  const [activeAgent, setActiveAgent] = useState<string | null>(null);

  useEffect(() => {
    // Generate or retrieve anonymous user session ID
    if (!localStorage.getItem("ai_analyst_user_id")) {
      localStorage.setItem("ai_analyst_user_id", crypto.randomUUID());
    }
    fetchConnections();
  }, []);

  const getHeaders = () => {
    return {
      "Content-Type": "application/json",
      "X-User-ID": localStorage.getItem("ai_analyst_user_id") || "anonymous"
    };
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const fetchConnections = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/connections`, {
        headers: { "X-User-ID": localStorage.getItem("ai_analyst_user_id") || "anonymous" }
      });
      if (res.ok) {
        const data = await res.json();
        setConnections(data);
        if (data.length > 0 && !activeConnectionId) {
          setActiveConnectionId(data[0].id);
        }
      }
    } catch (e: any) {
      console.error("Failed to fetch connections", e);
    }
  };

  const handleAddConnection = async () => {
    if (!newConnName || !newConnString) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/connections`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ name: newConnName, connection_string: newConnString }),
      });
      if (res.ok) {
        setIsConnDialogOpen(false);
        setNewConnName("");
        setNewConnString("");
        fetchConnections();
      } else {
        const errText = await res.text();
        alert(`Failed to save! API URL: ${API_BASE_URL}\nStatus: ${res.status}\nError: ${errText}`);
      }
    } catch (e: any) {
      console.error("Failed to add connection", e);
      alert(`Error saving connection: ${e.message}`);
    }
  };

  const handleDeleteConnection = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/connections/${id}`, { 
        method: "DELETE",
        headers: { "X-User-ID": localStorage.getItem("ai_analyst_user_id") || "anonymous" }
      });
      if (res.ok) {
        if (activeConnectionId === id) setActiveConnectionId("");
        fetchConnections();
      }
    } catch (e: any) {
      console.error("Failed to delete connection", e);
    }
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    };
    
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);
    setActiveAgent("routing");

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: userMsg.content,
          connection_id: activeConnectionId || null,
        }),
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const data = await res.json();
      
      let botContent = data.response;
      
      // Convert the backend's raw chart path into a perfectly rendered Markdown image!
      botContent = botContent.replace(
        /\[Chart Saved at: visualizations\/(.+?)\]/g, 
        `![Generated Chart](${API_BASE_URL}/downloads/visualizations/$1)`
      );
      
      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: botContent,
        timestamp: new Date(),
        agent: data.routed_agent || "data_quality",
      };
      
      setMessages((prev) => [...prev, botMsg]);
      setActiveAgent(null);
    } catch (error: any) {
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `**Error:** Failed to reach the AI engine.\n\n\`\`\`\n${error.message}\n\`\`\``,
        agent: "system",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
      setActiveAgent(null);
    } finally {
      setIsLoading(false);
    }
  };

  const getAgentColor = (agent?: string) => {
    switch (agent) {
      case "sql": return "bg-blue-500";
      case "data_analysis": return "bg-purple-500";
      case "etl": return "bg-orange-500";
      case "visualization": return "bg-pink-500";
      case "data_quality": return "bg-green-500";
      case "routing": return "bg-gray-500 animate-pulse";
      default: return "bg-slate-500";
    }
  };

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 overflow-hidden font-sans">
      
      {/* Sidebar */}
      <aside className="w-72 bg-slate-900 text-slate-100 flex flex-col border-r border-slate-800 shadow-xl z-10">
        <div className="p-6 pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2 mb-1">
            <DatabaseZap className="h-6 w-6 text-blue-400" />
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">AI Data Analyst</h1>
          </div>
          <p className="text-xs text-slate-400 font-medium">Enterprise Data Intelligence</p>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
          
          {/* Databases Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <Database className="h-3.5 w-3.5" />
                Databases
              </h2>
              <Dialog open={isConnDialogOpen} onOpenChange={setIsConnDialogOpen}>
                <DialogTrigger>
                  <div className="flex h-6 w-6 items-center justify-center rounded-md text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer">
                    <PlusCircle className="h-4 w-4" />
                  </div>
                </DialogTrigger>
                <DialogContent className="sm:max-w-[425px]">
                  <DialogHeader>
                    <DialogTitle>Add Database Connection</DialogTitle>
                  </DialogHeader>
                  <div className="grid gap-4 py-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Connection Name</label>
                      <Input 
                        placeholder="e.g. Production Data, Neon DB" 
                        value={newConnName} 
                        onChange={(e) => setNewConnName(e.target.value)} 
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Connection String (URI)</label>
                      <Input 
                        placeholder="postgresql://user:pass@host:5432/db" 
                        type="password"
                        value={newConnString} 
                        onChange={(e) => setNewConnString(e.target.value)} 
                      />
                    </div>
                  </div>
                  <Button onClick={handleAddConnection} className="w-full">Save Connection</Button>
                </DialogContent>
              </Dialog>
            </div>
            
            {connections.length === 0 ? (
              <div className="text-xs text-slate-500 italic p-3 bg-slate-800/50 rounded-md border border-slate-700/50">
                No connections configured. Add one to query your data.
              </div>
            ) : (
              <Select value={activeConnectionId} onValueChange={(val: any) => setActiveConnectionId(val || "")}>
                <SelectTrigger className="w-full bg-slate-800 border-slate-700 text-sm focus:ring-blue-500 h-9">
                  <SelectValue placeholder="Select a database" />
                </SelectTrigger>
                <SelectContent>
                  {connections.map(c => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            
            <div className="space-y-1 mt-2">
              {connections.map(c => (
                <div key={c.id} className="flex items-center justify-between p-2 rounded-md hover:bg-slate-800 group text-sm transition-colors">
                  <span className="truncate pr-2 text-slate-300 group-hover:text-white">{c.name}</span>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => handleDeleteConnection(c.id)}
                    className="h-6 w-6 opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 hover:bg-red-900/30 transition-all"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
          
          {/* Active Agent Status Section */}
          <div className="space-y-3">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
              <Activity className="h-3.5 w-3.5" />
              Engine Status
            </h2>
            <div className="p-3 bg-slate-800/80 rounded-md border border-slate-700 flex items-center gap-3 shadow-inner">
              <div className="relative flex h-3 w-3">
                {isLoading ? (
                  <>
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
                  </>
                ) : (
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                )}
              </div>
              <div className="text-sm font-medium">
                {isLoading ? (
                  <span className="text-blue-300 flex items-center gap-2">
                    {activeAgent === "routing" ? "Analyzing Intent..." : `Agent: ${activeAgent?.toUpperCase()}`}
                  </span>
                ) : (
                  <span className="text-slate-300">Idle / Ready</span>
                )}
              </div>
            </div>
          </div>
          
        </div>
        
        <div className="p-4 border-t border-slate-800 text-xs text-slate-500 flex justify-between items-center">
          <span>v1.0.0</span>
          <Settings className="h-4 w-4 cursor-pointer hover:text-slate-300 transition-colors" />
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col h-full bg-white relative">
        <div className="absolute inset-0 bg-[radial-gradient(#e5e7eb_1px,transparent_1px)] [background-size:16px_16px] opacity-30 pointer-events-none"></div>
        
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 z-10" ref={scrollRef}>
          <div className="max-w-4xl mx-auto space-y-6 pb-20">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex gap-4 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                
                {msg.role === "assistant" && (
                  <Avatar className="h-9 w-9 border-2 border-slate-100 shadow-sm shrink-0 mt-1">
                    <div className="h-full w-full bg-blue-600 flex items-center justify-center text-white">
                      <Bot className="h-5 w-5" />
                    </div>
                  </Avatar>
                )}
                
                <div className={`flex flex-col gap-1 max-w-[85%] ${msg.role === "user" ? "items-end" : "items-start"}`}>
                  
                  {msg.role === "assistant" && msg.agent && (
                    <div className="flex items-center gap-2 ml-1">
                      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                        {msg.agent.replace('_', ' ')} Agent
                      </span>
                      <div className={`h-2 w-2 rounded-full ${getAgentColor(msg.agent)}`} />
                    </div>
                  )}

                  <div className={`relative px-5 py-4 rounded-2xl shadow-sm border ${
                    msg.role === "user" 
                      ? "bg-blue-600 text-white border-blue-700 rounded-tr-sm" 
                      : "bg-white text-slate-800 border-slate-200 rounded-tl-sm"
                  }`}>
                    <div className={`prose prose-sm max-w-none ${msg.role === "user" ? "prose-invert" : "prose-slate"}
                      prose-p:leading-relaxed prose-pre:bg-slate-900 prose-pre:text-slate-50 
                      prose-th:border prose-th:border-slate-300 prose-th:bg-slate-100 prose-th:p-2
                      prose-td:border prose-td:border-slate-200 prose-td:p-2
                    `}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  </div>
                  
                  <span className="text-[10px] text-slate-400 font-medium px-1 mt-1">
                    {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                {msg.role === "user" && (
                  <Avatar className="h-9 w-9 border-2 border-slate-100 shadow-sm shrink-0 mt-1">
                    <div className="h-full w-full bg-slate-800 flex items-center justify-center text-white">
                      <User className="h-5 w-5" />
                    </div>
                  </Avatar>
                )}
              </div>
            ))}
            
            {isLoading && (
              <div className="flex gap-4 justify-start animate-in fade-in slide-in-from-bottom-2 duration-300">
                <Avatar className="h-9 w-9 border-2 border-slate-100 shadow-sm shrink-0 mt-1">
                  <div className="h-full w-full bg-blue-600 flex items-center justify-center text-white">
                    <Bot className="h-5 w-5" />
                  </div>
                </Avatar>
                <div className="flex flex-col gap-1 items-start">
                  <div className="px-5 py-4 rounded-2xl rounded-tl-sm bg-white border border-slate-200 shadow-sm flex items-center gap-3">
                    <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                    <span className="text-sm font-medium text-slate-600">
                      {activeAgent === "routing" ? "Supervising and routing request..." : "Generating analysis..."}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white/80 backdrop-blur-md border-t border-slate-200 z-20">
          <div className="max-w-4xl mx-auto relative flex items-center gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder={connections.length === 0 ? "Please add a database connection first..." : "Ask your AI Data Analyst..."}
              className="pr-12 h-14 bg-white shadow-sm border-slate-300 focus-visible:ring-blue-500 rounded-xl text-base"
              disabled={isLoading || connections.length === 0}
            />
            <Button 
              size="icon" 
              onClick={handleSend} 
              disabled={!input.trim() || isLoading || connections.length === 0}
              className="absolute right-2 h-10 w-10 rounded-lg bg-blue-600 hover:bg-blue-700 transition-all shadow-sm"
            >
              <Send className="h-4 w-4 text-white" />
            </Button>
          </div>
          <div className="max-w-4xl mx-auto mt-2 text-center">
            <span className="text-[10px] text-slate-400 font-medium tracking-wide uppercase">
              Powered by Advanced Agentic Routing (ETL, SQL, Visualization, Deep Analysis)
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}

// A simple local Avatar component wrapper since we might not have installed shadcn avatar correctly
function Avatar({ children, className }: { children: React.ReactNode, className?: string }) {
  return (
    <div className={`relative flex shrink-0 overflow-hidden rounded-full ${className}`}>
      {children}
    </div>
  )
}
