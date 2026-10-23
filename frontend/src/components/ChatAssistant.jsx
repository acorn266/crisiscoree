import { useEffect, useRef, useState } from 'react';
import { sendChat } from '../services/api';

const SAMPLE_QUESTIONS = [
  'What should I do during an earthquake?',
  'How do I prepare for a flood?',
  'Is there any earthquake activity near India right now?',
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
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    ask(input);
  };

  return (
    <section className="card assistant">
      <div className="assistant-icon">🤖</div>
      <div className="assistant-content">
        <h2>CrisisCore AI Assistant</h2>
        <p>
          Ask about current disaster conditions, safety, emergency resources, or preparedness.
          Answers use live dashboard data; built-in safety guidance is used if the AI is unavailable.
        </p>

        {messages.length === 0 ? (
          <div className="chat-suggestions">
            {SAMPLE_QUESTIONS.map((q) => (
              <button key={q} type="button" className="chat-chip" onClick={() => ask(q)} disabled={sending}>
                {q}
              </button>
            ))}
          </div>
        ) : (
          <div className="chat-log" ref={logRef} aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={`chat-msg chat-msg-${m.role}`}>
                {m.notice && <small className="chat-notice">ⓘ {m.notice}</small>}
                <div className="chat-text">{m.text}</div>
              </div>
            ))}
            {sending && (
              <div className="chat-msg chat-msg-assistant">
                <div className="chat-text chat-typing">Thinking…</div>
              </div>
            )}
          </div>
        )}

        <form className="chat-input" onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Ask: What should I do during an earthquake?"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={1000}
            disabled={sending}
            aria-label="Ask the CrisisCore AI Assistant"
          />
          <button type="submit" disabled={sending || !input.trim()}>
            {sending ? 'Asking…' : 'Ask AI'}
          </button>
        </form>
      </div>
    </section>
  );
}

export default ChatAssistant;
