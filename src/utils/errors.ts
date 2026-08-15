export interface Error {
  parent: string
  type: string
  details?: unknown
  message: string
}

function isError(value: unknown): value is Error {
  return (
    typeof value === "object" &&
    value !== null &&
    "parent" in value &&
    "type" in value &&
    "message" in value
  )
}


export function getErrorMessage(t: (key: string, params?: unknown) => string, error: unknown): string {
  if (typeof error === "string") {
    try {
      const data = JSON.parse(error)
      if (isError(data)) error = data
    } catch {
      return String(error) || t("errors.AppError.Unknown")
    }
  }

  if (isError(error)) {
    const params = error.details && typeof error.details === "object"
      ? error.details
      : { details: error.details }
    if (error.type === "Io") {
      const { kind } = error.details as { kind: string }
      return t(`errors.Io.${kind}`)
    }
    return t(`errors.${error.parent}.${error.type}`, { ...params, defaultValue: error.message })
  }

  if (error instanceof Error) return error.message
  return t("errors.AppError.Unknown")
}
