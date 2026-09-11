import { defineStore } from "pinia";
import { readonly, ref } from "vue";
import { attachLogger, LogLevel as TauriLogLevel } from '@tauri-apps/plugin-log'

const LOG_TO_CONSOLE = true;

export enum LogLevel {
    Debug = 'Debug',
    Info = 'Info',
    Warning = 'Warning',
    Error = 'Error',
}

export enum LogSource {
    Backend = 'Backend',
    Frontend = 'Frontend'
}

interface LogMessage {
    source: LogSource
    level: LogLevel;
    message: string;
    timestamp: Date;
    caller?: string;
}

const SELF_URL = import.meta.url

function getFileName(path: string): string {
    return path.split(/[\\/]/).pop()?.split(/[?#]/)[0] || path
}

function getCallerLocation(): string | undefined {
    if (!import.meta.env.DEV) return undefined

    const stack = new Error().stack
    if (!stack) return undefined

    const isNoise = (line: string) =>
        /pinia/i.test(line) || /node_modules/.test(line) || line.includes(SELF_URL)

    if (stack.startsWith('Error')) {
        const lines = stack.split('\n').slice(1)
        const callerLine = lines.find((line) => !isNoise(line))?.trim()
        if (!callerLine) return undefined

        const regex = /at\s+(?<functionName>.*?)\s+\((?<fileName>.*?):(?<lineNumber>\d+):(?<columnNumber>\d+)\)/
        const match = callerLine.match(regex)
        if (match) {
            const { functionName, fileName, lineNumber, columnNumber } = match.groups as {
                functionName: string
                fileName: string
                lineNumber: string
                columnNumber: string
            }
            return `${functionName}@${getFileName(fileName)}:${lineNumber}:${columnNumber}`
        }

        const regexNoFunction = /at\s+(?<fileName>.*?):(?<lineNumber>\d+):(?<columnNumber>\d+)/
        const matchNoFunction = callerLine.match(regexNoFunction)
        if (matchNoFunction) {
            const { fileName, lineNumber, columnNumber } = matchNoFunction.groups as {
                fileName: string
                lineNumber: string
                columnNumber: string
            }
            return `<anonymous>@${getFileName(fileName)}:${lineNumber}:${columnNumber}`
        }

        return undefined
    }

    const traces = stack.split('\n').map((line) => line.split('@'))
    const filtered = traces.filter(
        ([name, location]) =>
            name.length > 0 && location !== '[native code]' && !isNoise(location ?? '')
    )
    const [functionName, location] = filtered[0] ?? []
    if (!functionName || !location) return undefined

    const match = location.match(/(?<fileName>.*?):(?<lineNumber>\d+):(?<columnNumber>\d+)$/)
    if (!match?.groups) return undefined

    const { fileName, lineNumber, columnNumber } = match.groups
    return `${functionName}@${getFileName(fileName)}:${lineNumber}:${columnNumber}`
}

function mapTauriLevel(level: TauriLogLevel): LogLevel {
    switch (level) {
        case TauriLogLevel.Trace:
            return LogLevel.Debug;
        case TauriLogLevel.Debug:
            return LogLevel.Debug;
        case TauriLogLevel.Info:
            return LogLevel.Info;
        case TauriLogLevel.Warn:
            return LogLevel.Warning;
        case TauriLogLevel.Error:
            return LogLevel.Error;
        default:
            return LogLevel.Info;
    }
}

export const useLoggingStore = defineStore("logging", () => {
    const logs = ref<LogMessage[]>([]);

    function addLog(level: LogLevel, message: string, source?: LogSource, caller?: string) {
        const timestamp = new Date();
        const resolvedSource = source ?? LogSource.Frontend;
        logs.value.push({ source: resolvedSource, level, message, timestamp, caller });

        if (LOG_TO_CONSOLE && source === LogSource.Frontend) {
            const callerStr = caller ? ` [${caller}]` : ''
            if (!import.meta.env.DEV) return
            console.log(`[${timestamp}] [${resolvedSource}] [${level.toUpperCase()}]${callerStr} ${message}`);
        }
    }

    function logInfo(...args: any[]) {
        addLog(LogLevel.Info, args.join(" "), LogSource.Frontend, getCallerLocation());
    }

    function logWarning(...args: any[]) {
        addLog(LogLevel.Warning, args.join(" "), LogSource.Frontend, getCallerLocation());
    }

    function logError(...args: any[]) {
        addLog(LogLevel.Error, args.join(" "), LogSource.Frontend, getCallerLocation());
    }

    function logDebug(...args: any[]) {
        addLog(LogLevel.Debug, args.join(" "), LogSource.Frontend, getCallerLocation());
    }

    function clearLogs() {
        logs.value = [];
    }

    let detachLogger: (() => void) | null = null;

    attachLogger(({ level, message }) => {
        addLog(mapTauriLevel(level), message, LogSource.Backend);
    }).then((unlisten) => {
        detachLogger = unlisten;
    });

    function detach() {
        detachLogger?.();
        detachLogger = null;
    }

    return {
        logs: readonly(logs),
        logInfo,
        logWarning,
        logError,
        logDebug,
        clearLogs,
        detach,
    };
});
