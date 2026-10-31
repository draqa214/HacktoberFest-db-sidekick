import Brand from "./Brand";

export default function AuthAside() {
  return <aside className="auth-story">
    <Brand />
    <div className="auth-story-copy">
      <span className="eyebrow">A LITTLE CLARITY. A LOT LESS SQL.</span>
      <h2>Big questions.<br/><span>Clear answers.</span></h2>
      <p>Explore your data, turn diagrams into tables, and make changes with confidence. Your sidekick handles the SQL. You stay in control.</p>
      <div className="schema-art" aria-label="Illustration of related database tables">
        <div className="schema-node"><strong><i/>customers</strong><span><b>PK</b> id <em>uuid</em></span><span>name <em>text</em></span><span>city <em>text</em></span></div>
        <div className="schema-connector" aria-hidden="true"><span>1</span><i/><span>∞</span></div>
        <div className="schema-node schema-node-offset"><strong><i/>orders</strong><span><b>PK</b> id <em>uuid</em></span><span><b>FK</b> customer_id <em>uuid</em></span><span>total <em>numeric</em></span></div>
        <div className="schema-note"><span>✓</span> A little context goes a long way.</div>
      </div>
    </div>
    <div className="auth-story-footer"><span className="status-dot"/> Built for thoughtful database work.</div>
  </aside>;
}
