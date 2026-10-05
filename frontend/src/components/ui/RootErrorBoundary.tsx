import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: Error | null };

export default class RootErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Application error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-slate-100 p-8 flex items-start justify-center">
          <div className="max-w-lg w-full rounded-lg border border-red-200 bg-white p-6 shadow-sm text-slate-900">
            <h1 className="text-lg font-semibold text-red-800 mb-2">Something went wrong</h1>
            <p className="text-sm text-slate-700 mb-4 font-mono break-all">{this.state.error.message}</p>
            <button
              type="button"
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50"
              onClick={() => window.location.assign("/")}
            >
              Reload dashboard
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
