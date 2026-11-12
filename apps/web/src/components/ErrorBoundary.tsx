import { AlertTriangle, Home, RefreshCw, RotateCcw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public override state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("Uncaught error in React component tree:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  private handleReload = () => {
    window.location.reload();
  };

  private handleGoHome = () => {
    window.location.href = "/";
  };

  public override render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          role="alert"
          aria-live="assertive"
          className="w-full min-h-[400px] flex items-center justify-center p-6 animate-in fade-in duration-200"
        >
          <div className="w-full max-w-lg p-6 sm:p-8 rounded-card bg-surface border border-danger/30 shadow-card flex flex-col items-center text-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-danger/10 border border-danger/20 flex items-center justify-center text-danger shrink-0 shadow-xs">
              <AlertTriangle className="w-6 h-6" aria-hidden="true" />
            </div>

            <div className="flex flex-col gap-1.5 max-w-md">
              <h2 className="text-lg font-bold text-foreground tracking-tight">
                Terjadi Kesalahan pada Antarmuka
              </h2>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Aplikasi mengalami kendala tak terduga saat memuat bagian ini. Anda dapat mencoba
                memuat ulang komponen atau kembali ke beranda.
              </p>
            </div>

            {this.state.error?.message && (
              <div className="w-full p-3 rounded-xl bg-surface-user border border-border/80 text-left">
                <span className="text-[10px] uppercase font-mono text-muted-foreground block mb-1">
                  Detail Error
                </span>
                <p className="text-xs font-mono text-danger break-words">
                  {this.state.error.message}
                </p>
              </div>
            )}

            <div className="flex flex-wrap items-center justify-center gap-2.5 pt-2 w-full">
              <Button
                variant="outline"
                size="sm"
                onClick={this.handleReset}
                className="gap-1.5 text-xs"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Coba Lagi</span>
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={this.handleReload}
                className="gap-1.5 text-xs"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Muat Ulang Halaman</span>
              </Button>

              <Button
                variant="default"
                size="sm"
                onClick={this.handleGoHome}
                className="gap-1.5 text-xs"
              >
                <Home className="w-3.5 h-3.5" />
                <span>Ke Beranda</span>
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
