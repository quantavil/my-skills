import { api } from './run';

declare global {
  interface Window {
    impexFill: typeof api;
  }
}

window.impexFill = api;
