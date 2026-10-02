import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error in component tree:", error, errorInfo);
    this.setState({ errorInfo });
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full flex items-center justify-center bg-background-primary p-6">
          <div className="bg-card border border-status-error/30 rounded-3xl p-8 max-w-2xl w-full shadow-2xl flex flex-col gap-6">
            <div className="flex items-center gap-4 text-status-error border-b border-status-error/20 pb-4">
              <AlertTriangle size={32} />
              <h1 className="text-2xl font-black tracking-widest">FATAL SYSTEM ERROR</h1>
            </div>
            
            <div>
              <h2 className="font-bold text-text-primary mb-2">Reason:</h2>
              <div className="bg-background-secondary p-4 rounded-xl font-mono text-sm text-status-error border border-border">
                {this.state.error?.message || 'Unknown render error occurred.'}
              </div>
            </div>

            <div>
              <h2 className="font-bold text-text-primary mb-2">Suggested Fix:</h2>
              <div className="bg-background-secondary p-4 rounded-xl font-mono text-sm text-text-primary border border-border">
                1. Check if the backend services are running properly.
                <br/>2. Ensure network connectivity between the desktop and the hardware.
                <br/>3. Restart the SignalSense-Pro application.
              </div>
            </div>

            <button 
              onClick={() => window.location.reload()}
              className="mt-4 w-full py-4 bg-status-error/10 hover:bg-status-error text-status-error hover:text-white border border-status-error/50 rounded-xl font-bold tracking-widest flex items-center justify-center gap-3 transition-all"
            >
              <RefreshCw size={20} /> RETRY / RELOAD SYSTEM
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
