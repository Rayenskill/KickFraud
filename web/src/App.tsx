import { ReviewQueue } from "./ReviewQueue";
import { RingGraph } from "./RingGraph";
import { Filters } from "./Filters";

// SCAFFOLD shell. Layout/wiring filled in during the H2-H10 UI window.
export function App() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", height: "100vh" }}>
      <section>
        <Filters />
        <ReviewQueue />
      </section>
      <aside>
        <RingGraph />
      </aside>
    </div>
  );
}
