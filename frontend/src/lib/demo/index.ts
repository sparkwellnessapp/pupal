/**
 * Demo-mode event logger (`?demo=1`). The only module that knows demo mode
 * exists — see `core.ts` for the rules, `events.ts` for the derived events.
 * The root layout mounts `./DemoLogProvider` directly (a client component; it
 * is kept out of this barrel so plain call sites do not import the router).
 */
export { demoLog, exportLog, isDemo, resetLog } from './core';
export type { DemoEvent, DemoHeader, DemoLogFile, DemoMeta, DemoRect } from './core';
export {
    demoBatchZipDownloaded, demoFeedbackViewOpened, demoObserveScores, demoPdfDownloaded,
    demoTestApproved, observeBatch,
} from './events';
