import { useEffect, useRef, useState } from 'react';
import { sendChat } from '../services/api';

const SAMPLE_QUESTIONS = [
  'What should I do during an earthquake?',
  'Are there any earthquakes inside India right now?',
  'Are there any official flood warnings?',
  'Where is the nearest hospital?',
  'What are the signs of heat stroke?',
];

const OFFLINE_REPLY =
  "I can't reach the CrisisCore server right now. In an emergency call 112. " +
  'For earthquakes: Drop, Cover and Hold On. For floods: move to higher ground and avoid flood water.';

function ChatAssistant({ context }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const logRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages, sending]);

  const ask = async (text) => {
    const question = text.trim();
    if (!question || sending) return;

    const history = messages
      .filter((m) => m.role === 'user' || m.source === 'gemini')
      .slice(-6)
      .map(({ role, text: t }) => ({ role, text: t }));

    setMessages((prev) => [...prev, { role: 'user', text: question }]);
    setInput('');
    setSending(true);

    try {
      const data = await sendChat(question, history, context);
      setMessages((prev) => [...prev, {
        role: 'assistant',
        text: data.reply,
        source: data.source,
        notice: data.notice,
      }]);
    } catch (err) {
      console.warn('Chat request failed:', err);
      setMessages((prev) => [...prev, {
        role: 'assistant',
        text: OFFLINE_REPLY,
        source: 'error',
        notice: 'Connection problem — showing basic safety tips.',
      }]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    ask(input);
  };

  const lastSource = [...messages].reverse().find((m) => m.role === 'assistant')?.source;

  return (
    <section className="card chat-card" aria-label="CrisisCore AI Assistant">
      <header className="chat-header">
        <div className="chat-avatar" aria-hidden="true">🛡</div>
        <div className="chat-heading">
          <h2>CrisisCore AI Assistant</h2>
          <p className="card-sub">
            Answers use this dashboard&apos;s live data · Google Gemini (free tier) with a built-in offline safety guide
          </p>
        </div>
        <div className="chat-header-side">
          <span className={`data-tag ${lastSource === 'fallback' || lastSource === 'error' ? 'tag-saved' : 'tag-ai'}`}>
            {lastSource === 'fallback' ? 'Offline guide' : lastSource === 'error' ? 'Offline' : 'Gemini'}
          </span>
          {messages.length > 0 && (
            <button type="button" className="btn btn-ghost btn-small" onClick={() => setMessages([])} disabled={sending}>
              Clear
            </button>
          )}
        </div>
      </header>

      <div className="chat-log" ref={logRef} aria-live="polite">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <p>Ask about current alerts, safety steps, or the nearest emergency resources.</p>
            <div className="chat-suggestions">
              {SAMPLE_QUESTIONS.map((q) => (
                <button key={q} type="button" className="chip chat-chip" onClick={() => ask(q)} disabled={sending}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-row chat-row--${m.role}`}>
            {m.role === 'assistant' && <div className="chat-bubble-avatar" aria-hidden="true">🛡</div>}
            <div className={`chat-msg chat-msg-${m.role}`}>
              {m.notice && <small className="chat-notice">ⓘ {m.notice}</small>}
              <div className="chat-text">{m.text}</div>
            </div>
          </div>
        ))}
        {sending && (
          <div className="chat-row chat-row--assistant">
            <div className="chat-bubble-avatar" aria-hidden="true">🛡</div>
            <div className="chat-msg chat-msg-assistant chat-typing" aria-label="Assistant is typing">
              <span /><span /><span />
            </div>
          </div>
        )}
      </div>

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          placeholder="Ask about alerts, safety steps or nearby help…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={1000}
          disabled={sending}
          aria-label="Ask the CrisisCore AI Assistant"
        />
        <button type="submit" className="btn btn-primary" disabled={sending || !input.trim()}>
          {sending ? 'Asking…' : 'Send'}
        </button>
      </form>
      <p className="chat-disclaimer">AI answers can be wrong. In an emergency call <b>112</b> and follow official IMD / NDMA advisories.</p>
    </section>
  );
}

export default ChatAssistant;
