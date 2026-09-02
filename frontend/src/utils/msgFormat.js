import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({
  gfm: true,
  breaks: true,
})

const FORMAT_MAP = {
  txt: 'txt',
  text: 'txt',
  plain: 'txt',
  markdown: 'markdown',
  md: 'markdown',
  html: 'html',
}

const HTML_TAG_RE = /<\/?(?:p|div|br|span|ul|ol|li|h[1-6]|table|tr|td|th|a|strong|em|b|i|pre|code|blockquote)\b/i
const MD_HINT_RE = /(?:^|\n)\s{0,3}#{1,6}\s|(?:^|\n)\s*[-*+]\s|(?:^|\n)\s*\d+\.\s|\*\*[^*\n]+\*\*|__[^_\n]+__|```|`[^`\n]+`|\[[^\]]+\]\([^)]+\)/

/**
 * Normalize format string to txt | markdown | html.
 */
export function normalizeFormat(format) {
  if (!format) return null
  return FORMAT_MAP[String(format).toLowerCase().trim()] || null
}

/**
 * Resolve content format from explicit field or heuristics.
 * @param {string|object} contentOrFormat - content object or format string
 * @param {string} [text] - optional text when first arg is format
 */
export function resolveFormat(contentOrFormat, text) {
  let format = null
  let body = text
  if (contentOrFormat && typeof contentOrFormat === 'object') {
    format = normalizeFormat(contentOrFormat.format)
    body = body ?? contentOrFormat.text ?? ''
  } else if (typeof contentOrFormat === 'string' && text === undefined) {
    body = contentOrFormat
  } else {
    format = normalizeFormat(contentOrFormat)
  }
  if (format) return format
  return detectFormat(String(body ?? ''))
}

export function detectFormat(text) {
  const s = String(text || '').trim()
  if (!s) return 'txt'
  if (s.startsWith('<') && HTML_TAG_RE.test(s)) return 'html'
  if (MD_HINT_RE.test(s)) return 'markdown'
  return 'txt'
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const PURIFY_OPTS = {
  USE_PROFILES: { html: true },
  ALLOWED_TAGS: [
    'a', 'b', 'strong', 'i', 'em', 'u', 's', 'del', 'p', 'br', 'hr',
    'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'span', 'div',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img',
  ],
  ALLOWED_ATTR: ['href', 'title', 'target', 'rel', 'src', 'alt', 'class'],
  ALLOW_DATA_ATTR: false,
}

function sanitize(html) {
  if (typeof DOMPurify?.sanitize !== 'function' || DOMPurify.isSupported === false) {
    return escapeHtml(html)
  }
  const clean = DOMPurify.sanitize(html, PURIFY_OPTS)
  // Ensure external links open safely
  if (typeof document !== 'undefined') {
    const wrap = document.createElement('div')
    wrap.innerHTML = clean
    wrap.querySelectorAll('a[href]').forEach((a) => {
      a.setAttribute('target', '_blank')
      a.setAttribute('rel', 'noopener noreferrer')
    })
    return wrap.innerHTML
  }
  return clean
}

/**
 * Render message body to safe HTML string (for markdown/html).
 * For txt, prefer plain text node in the component instead.
 */
export function renderMessageHtml(text, format) {
  const f = normalizeFormat(format) || detectFormat(text)
  const raw = String(text ?? '')
  if (f === 'txt') {
    return escapeHtml(raw).replace(/\n/g, '<br>')
  }
  if (f === 'markdown') {
    const html = marked.parse(raw, { async: false })
    return sanitize(typeof html === 'string' ? html : String(html))
  }
  return sanitize(raw)
}
