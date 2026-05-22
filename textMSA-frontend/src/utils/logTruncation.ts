/**
 * Log truncation utility for execution logs.
 * Implements requirement R5 for handling large execution logs with truncation.
 */

export interface LogTruncationOptions {
  /**
   * Maximum number of lines to show before truncation (default: 100)
   */
  maxLines?: number
  /**
   * Maximum number of characters to show before truncation (default: 10000)
   * This is a fallback if maxLines is not applicable
   */
  maxChars?: number
  /**
   * Whether to truncate from the beginning (oldest) or end (newest) (default: 'end')
   * 'end' keeps the most recent lines, 'start' keeps the oldest lines
   */
  truncateFrom?: 'start' | 'end'
}

const DEFAULT_OPTIONS: Required<LogTruncationOptions> = {
  maxLines: 100,
  maxChars: 10000,
  truncateFrom: 'end'
}

/**
 * Truncate a log string based on line count or character count.
 * Returns the truncated log and whether truncation occurred.
 */
export function truncateLog(
  log: string | null | undefined,
  options: LogTruncationOptions = {}
): { truncated: string; wasTruncated: boolean; originalLength: number } {
  if (!log) {
    return { truncated: '', wasTruncated: false, originalLength: 0 }
  }

  const opts = { ...DEFAULT_OPTIONS, ...options }
  const originalLength = log.length
  let truncated = log
  let wasTruncated = false

  // First, try truncating by lines
  if (opts.maxLines > 0) {
    const lines = log.split('\n')
    if (lines.length > opts.maxLines) {
      wasTruncated = true
      if (opts.truncateFrom === 'end') {
        // Keep the last N lines
        truncated = lines.slice(-opts.maxLines).join('\n')
      } else {
        // Keep the first N lines
        truncated = lines.slice(0, opts.maxLines).join('\n')
      }
    }
  }

  // Then, apply character limit if still needed
  if (opts.maxChars > 0 && truncated.length > opts.maxChars) {
    wasTruncated = true
    if (opts.truncateFrom === 'end') {
      // Keep the last N characters
      truncated = truncated.slice(-opts.maxChars)
    } else {
      // Keep the first N characters
      truncated = truncated.slice(0, opts.maxChars)
    }
  }

  return {
    truncated,
    wasTruncated: wasTruncated || originalLength !== truncated.length,
    originalLength
  }
}

/**
 * Format a truncated log with expand/collapse indicators.
 * Returns the formatted log and metadata.
 */
export function formatTruncatedLog(
  log: string | null | undefined,
  options: LogTruncationOptions & { expanded?: boolean } = {}
): {
  display: string
  wasTruncated: boolean
  originalLength: number
  truncatedLength: number
  canExpand: boolean
} {
  const { expanded = false, ...truncateOptions } = options

  if (expanded || !log) {
    return {
      display: log || '',
      wasTruncated: false,
      originalLength: log?.length || 0,
      truncatedLength: log?.length || 0,
      canExpand: false
    }
  }

  const { truncated, wasTruncated, originalLength } = truncateLog(log, truncateOptions)

  return {
    display: truncated,
    wasTruncated,
    originalLength,
    truncatedLength: truncated.length,
    canExpand: wasTruncated
  }
}

/**
 * Get a human-readable size description for a log.
 */
export function getLogSizeDescription(length: number): string {
  if (length < 1024) {
    return `${length} 字符`
  } else if (length < 1024 * 1024) {
    return `${(length / 1024).toFixed(1)} KB`
  } else {
    return `${(length / (1024 * 1024)).toFixed(2)} MB`
  }
}


