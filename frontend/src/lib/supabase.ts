import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
console.log("Check URL Netlify cấp:", supabaseUrl);
console.log("Check KEY Netlify cấp:", supabaseAnonKey ? "CÓ KEY (Độ dài: " + supabaseAnonKey.length + ")" : "TRỐNG TRƠN (UNDEFINED)");
if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY env vars');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
