import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: Error | null };

export default class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Route render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="max-w-2xl rounded-lg border border-red-200 bg-red-50 p-4 text-red-900">
          <p className="font-medium mb-2">This page could not be displayed</p>
          <p className="text-sm mb-3 font-mono break-all">{this.state.error.message}</p>
          <div className="flex gap-2">
            <button type="button" className="aq-btn-secondary" onClick={() => this.setState({ error: null })}>
              Try again
            </button>
            <a href="/" className="aq-btn-secondary inline-flex">
              Dashboard
            </a>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
