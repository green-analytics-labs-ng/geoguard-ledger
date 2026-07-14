import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

// Catches render-time errors in the component tree so a single broken page
// does not white-screen the whole app. Shows a recoverable fallback instead.
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("Uncaught error in GeoGuard Ledger UI:", error, errorInfo);
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          style={{
            maxWidth: "32rem",
            margin: "4rem auto",
            padding: "2rem",
            textAlign: "center",
            borderRadius: "12px",
            border: "1px solid var(--border, #e5e7eb)",
            background: "var(--surface, #ffffff)",
          }}
        >
          <h1 style={{ fontSize: "1.5rem", marginBottom: "0.75rem" }}>Something went wrong</h1>
          <p style={{ color: "var(--text-secondary, #6b7280)", marginBottom: "1.5rem" }}>
            An unexpected error occurred while rendering this page.
          </p>
          <button type="button" onClick={this.handleReset} style={{ cursor: "pointer" }}>
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
