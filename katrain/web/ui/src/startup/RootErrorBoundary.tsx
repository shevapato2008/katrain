import { Component, type ReactNode } from 'react';
import { StartupFailure } from './StartupState';
import { recordStartupFailure } from './startupDiagnostics';

type Props = { children: ReactNode; onRetry?: () => void };
type State = { renderFailed: boolean; preloadFailed: boolean };

export default class RootErrorBoundary extends Component<Props, State> {
  state: State = { renderFailed: false, preloadFailed: false };

  static getDerivedStateFromError(): Partial<State> {
    return { renderFailed: true };
  }

  componentDidCatch() {
    recordStartupFailure('render');
  }

  componentDidMount() {
    window.addEventListener('vite:preloadError', this.handlePreloadFailure);
  }

  componentWillUnmount() {
    window.removeEventListener('vite:preloadError', this.handlePreloadFailure);
  }

  private handlePreloadFailure = (event: Event) => {
    event.preventDefault();
    recordStartupFailure('preload');
    this.setState({ preloadFailed: true });
  };

  private retry = () => {
    if (this.props.onRetry) this.props.onRetry();
    else window.location.reload();
  };

  render() {
    if (this.state.renderFailed) return <StartupFailure category="render" onRetry={this.retry} />;
    return <>
      {this.props.children}
      {this.state.preloadFailed && <StartupFailure category="preload" onRetry={this.retry} />}
    </>;
  }
}
