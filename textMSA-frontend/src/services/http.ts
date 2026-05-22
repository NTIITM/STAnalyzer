/**
 * Lightweight re-export of the shared HTTP client used by service modules.
 * Keeps service-layer imports decoupled from the underlying request implementation.
 */
export { default } from '../api/request'
export * from '../api/request'

