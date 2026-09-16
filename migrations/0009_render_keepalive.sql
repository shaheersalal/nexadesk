-- Render's free tier sleeps after 15 min without inbound traffic and takes
-- ~50s to wake, but Twilio abandons the voice webhook after 15s, so any call
-- after a quiet spell failed with a 502. Ping /health every 10 min to keep it
-- awake. One instance running 24/7 (~744h) fits the 750 free hours a month.
-- Remove with: select cron.unschedule('render-keepalive');
create extension if not exists pg_cron;
select cron.schedule(
  'render-keepalive',
  '*/10 * * * *',
  $$select net.http_get(
      url := 'https://nexadesk-api-xx1h.onrender.com/health',
      headers := '{"User-Agent": "Mozilla/5.0 (compatible; nexadesk-keepalive)"}'::jsonb,
      timeout_milliseconds := 30000
  )$$
);
