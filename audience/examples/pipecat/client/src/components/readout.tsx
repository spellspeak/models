import { Panel } from "@/components/panel";
import { labelOf } from "@/cast";
import { useRoom } from "@/store";
import type { PlanInfo } from "@/types";

function planText(plan: PlanInfo): string {
  const who = plan.speakers.map((s) => labelOf(s).toLowerCase()).join(", ");
  switch (plan.why) {
    case "chorus":
      return `everyone, all at once: ${who}`;
    case "group":
      return `everyone, in turn: ${who}`;
    case "several":
      return `${who}, in turn`;
    case "unclear":
      return `unclear: ${who} ${plan.speakers.length > 1 ? "ask" : "asks"} "who, me?"`;
    case "fallback":
      return `${who} (not sure: whoever you spoke with last)`;
    default:
      return who;
  }
}

/** What Audience heard, and what the room did with your last turn. */
export function Readout() {
  const engine = useRoom((s) => s.engine);
  const reading = useRoom((s) => s.reading);
  const plan = useRoom((s) => s.plan);
  const looking = useRoom((s) => s.looking);

  return (
    <Panel
      title="targeting"
      status={
        engine && (
          <span
            className={engine.engine === "model" ? "text-active" : "text-tool"}
          >
            {engine.engine === "model"
              ? `model ${engine.release}`
              : "rules baseline"}
          </span>
        )
      }
      footnote={
        reading && (
          <span className="tabular-nums">{reading.ms.toFixed(1)} ms</span>
        )
      }
      className="flex min-h-0 flex-1 basis-0 flex-col"
    >
      {/* Scrolls inside the border, so the labels sitting on it aren't clipped. */}
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-4 pt-5 pb-4 text-[12px] leading-[1.55]">
        <p className="min-h-5 text-foreground">
          <span className="text-client">❯ </span>
          {reading ? (
            <>
              {reading.heard}
              {!reading.final && (
                <span className="animate-blink text-client">▌</span>
              )}
            </>
          ) : (
            <span className="text-muted-foreground/60">
              say something, to one of them or to everyone
            </span>
          )}
        </p>
        <p className="text-muted-foreground">
          <span className="text-agent">→ </span>
          {plan ? (
            <span className="text-foreground">{planText(plan)}</span>
          ) : (
            "—"
          )}
        </p>
        <p className="text-muted-foreground/70">
          gaze:{" "}
          {looking ? labelOf(looking).toLowerCase() : "nobody in particular"}
          <span className="text-muted-foreground/40">
            {" "}
            · click someone to look at them
          </span>
        </p>
      </div>
    </Panel>
  );
}
