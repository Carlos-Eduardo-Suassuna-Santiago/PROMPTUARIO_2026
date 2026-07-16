import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-6 text-center">
          <div className="w-16 h-16 bg-rose-500/10 text-rose-500 rounded-2xl flex items-center justify-center mb-6">
            <AlertTriangle className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-slate-100 mb-2">Ops! Algo deu errado.</h2>
          <p className="text-slate-400 mb-6 max-w-md">
            Um erro inesperado ocorreu ao carregar este componente. Se o problema persistir, entre em contato com o suporte.
          </p>
          <div className="flex gap-4">
            <Button onClick={() => window.location.reload()}>
              Recarregar página
            </Button>
            <Button onClick={() => window.location.href = '/'} variant="outline">
              Voltar ao Início
            </Button>
          </div>
          {import.meta.env.MODE === 'development' && this.state.error && (
            <pre className="mt-8 p-4 bg-slate-900 rounded-lg text-left text-rose-400 text-xs overflow-auto max-w-2xl w-full">
              {this.state.error.stack}
            </pre>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
