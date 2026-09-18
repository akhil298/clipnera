// GENERATED FILE - do not edit by hand.
// Mirrors backend/subtitle_styling/emoji_catalog.py, the canonical whitelist.
// Regenerate with: cd backend && python -m subtitle_styling.export_emoji_catalog

export interface EmojiCatalogEntry {
  slug: string;
  char: string;
  category: EmojiCategory;
  keywords: string[];
}

export type EmojiCategory =
  | "money"
  | "growth"
  | "mind"
  | "emotion"
  | "power"
  | "time"
  | "people"
  | "build"
  | "tech"
  | "life";

export const EMOJI_CATEGORIES: EmojiCategory[] = ["money", "growth", "mind", "emotion", "power", "time", "people", "build", "tech", "life"];

export const EMOJI_CATALOG: EmojiCatalogEntry[] = [
  { slug: "money", char: "💰", category: "money", keywords: ["money", "cash", "fund", "funds", "wealth", "payout"] },
  { slug: "banknote", char: "💵", category: "money", keywords: ["banknote", "dollar", "dollars", "income", "salary", "paid"] },
  { slug: "money_wings", char: "💸", category: "money", keywords: ["money_wings", "spend", "spending", "sell", "burn_cash", "expense"] },
  { slug: "credit_card", char: "💳", category: "money", keywords: ["credit_card", "debt", "loan", "credit", "subscription"] },
  { slug: "coin", char: "🪙", category: "money", keywords: ["coin", "crypto", "bitcoin", "token", "coins"] },
  { slug: "bank", char: "🏦", category: "money", keywords: ["bank", "savings", "save", "deposit", "interest"] },
  { slug: "money_face", char: "🤑", category: "money", keywords: ["money_face", "rich", "millionaire", "billionaire", "profitable"] },
  { slug: "gem", char: "💎", category: "money", keywords: ["gem", "valuable", "premium", "luxury", "diamond"] },
  { slug: "receipt", char: "🧾", category: "money", keywords: ["receipt", "tax", "taxes", "invoice", "bill"] },
  { slug: "shopping_cart", char: "🛒", category: "money", keywords: ["shopping_cart", "buy", "purchase", "customer", "customers", "sale"] },
  { slug: "price_tag", char: "🏷️", category: "money", keywords: ["price_tag", "price", "pricing", "discount", "offer"] },
  { slug: "free", char: "🆓", category: "money", keywords: ["free", "freebie", "no_cost", "zero_cost"] },
  { slug: "chart_up", char: "📈", category: "growth", keywords: ["chart_up", "growth", "grow", "growing", "profit", "revenue", "viral", "increase"] },
  { slug: "chart_down", char: "📉", category: "growth", keywords: ["chart_down", "decline", "drop", "loss", "crash", "decrease"] },
  { slug: "bar_chart", char: "📊", category: "growth", keywords: ["bar_chart", "data", "metrics", "analytics", "scale", "invest", "investment", "numbers"] },
  { slug: "trophy", char: "🏆", category: "growth", keywords: ["trophy", "win", "winning", "won", "success", "successful", "champion"] },
  { slug: "medal", char: "🥇", category: "growth", keywords: ["medal", "first", "best", "number_one", "winner", "top_spot"] },
  { slug: "target", char: "🎯", category: "growth", keywords: ["target", "goal", "goals", "focus", "aim", "precise", "bullseye"] },
  { slug: "check", char: "✅", category: "growth", keywords: ["check", "done", "achieve", "correct", "result", "results", "verified"] },
  { slug: "cross_mark", char: "❌", category: "growth", keywords: ["cross_mark", "wrong", "fail", "failure", "mistake", "avoid"] },
  { slug: "arrow_up", char: "⬆️", category: "growth", keywords: ["arrow_up", "upgrade", "higher", "raise", "level_up"] },
  { slug: "rocket", char: "🚀", category: "growth", keywords: ["rocket", "launch", "boost", "startup", "fast_growth", "space", "takeoff"] },
  { slug: "trending", char: "🔥", category: "growth", keywords: ["trending", "fire", "hot", "lit", "blazing"] },
  { slug: "hundred", char: "💯", category: "growth", keywords: ["hundred", "perfect_score", "hundred_percent", "all_in"] },
  { slug: "bulb", char: "💡", category: "mind", keywords: ["bulb", "idea", "ideas", "insight", "answer", "solution", "light", "tip"] },
  { slug: "brain", char: "🧠", category: "mind", keywords: ["brain", "smart", "genius", "mind", "knowledge", "intelligence", "remember"] },
  { slug: "thinking", char: "🤔", category: "mind", keywords: ["thinking", "think", "consider", "wonder", "hmm"] },
  { slug: "thought_bubble", char: "💭", category: "mind", keywords: ["thought_bubble", "thought", "imagine", "dream", "reflection"] },
  { slug: "books", char: "📚", category: "mind", keywords: ["books", "learn", "learning", "study", "education", "course"] },
  { slug: "open_book", char: "📖", category: "mind", keywords: ["open_book", "read", "reading", "book", "lesson", "chapter", "story"] },
  { slug: "graduation", char: "🎓", category: "mind", keywords: ["graduation", "school", "degree", "graduate", "university", "student"] },
  { slug: "question", char: "❓", category: "mind", keywords: ["question", "ask", "why", "unknown", "confused"] },
  { slug: "exclamation", char: "❗", category: "mind", keywords: ["exclamation", "important", "attention", "alert", "notice"] },
  { slug: "magnifier", char: "🔍", category: "mind", keywords: ["magnifier", "search", "discover", "find", "look_closer", "investigate"] },
  { slug: "microscope", char: "🔬", category: "mind", keywords: ["microscope", "science", "research", "experiment", "analysis"] },
  { slug: "memo", char: "📝", category: "mind", keywords: ["memo", "write", "note", "notes", "plan", "list"] },
  { slug: "key", char: "🔑", category: "mind", keywords: ["key", "unlock", "access", "secret_key", "solution_key", "critical"] },
  { slug: "puzzle", char: "🧩", category: "mind", keywords: ["puzzle", "piece", "fit", "complex", "solve"] },
  { slug: "mind_blown", char: "🤯", category: "emotion", keywords: ["mind_blown", "insane", "crazy", "incredible", "unbelievable", "shocked"] },
  { slug: "star_struck", char: "🤩", category: "emotion", keywords: ["star_struck", "amazing", "epic", "awesome", "stunning", "wow_good"] },
  { slug: "scream", char: "😱", category: "emotion", keywords: ["scream", "shocking", "scary", "fear", "terrified", "horror"] },
  { slug: "surprised", char: "😮", category: "emotion", keywords: ["surprised", "wow", "surprise", "unexpected", "whoa"] },
  { slug: "smile", char: "😄", category: "emotion", keywords: ["smile", "happy", "happiness", "joy", "glad"] },
  { slug: "laugh", char: "😂", category: "emotion", keywords: ["laugh", "funny", "hilarious", "lol", "joke", "comedy"] },
  { slug: "sad", char: "😢", category: "emotion", keywords: ["sad", "cry", "upset", "unhappy"] },
  { slug: "angry", char: "😡", category: "emotion", keywords: ["angry", "mad", "rage", "furious"] },
  { slug: "sunglasses", char: "😎", category: "emotion", keywords: ["sunglasses", "cool", "confident", "smooth", "chill"] },
  { slug: "heart_eyes", char: "😍", category: "emotion", keywords: ["heart_eyes", "beautiful", "gorgeous", "adore", "obsessed"] },
  { slug: "heart", char: "❤️", category: "emotion", keywords: ["heart", "love", "loved", "passion", "care"] },
  { slug: "broken_heart", char: "💔", category: "emotion", keywords: ["broken_heart", "heartbreak", "hurt", "breakup", "painful"] },
  { slug: "skull", char: "💀", category: "emotion", keywords: ["skull", "dead", "brutal", "savage", "dying", "cooked"] },
  { slug: "clown", char: "🤡", category: "emotion", keywords: ["clown", "foolish", "joke_person", "ridiculous", "embarrassing"] },
  { slug: "sweat", char: "😓", category: "emotion", keywords: ["sweat", "stressed", "anxious", "nervous", "pressure"] },
  { slug: "ok_hand", char: "👌", category: "emotion", keywords: ["ok_hand", "perfect", "nice", "exact", "spot_on"] },
  { slug: "star", char: "⭐", category: "emotion", keywords: ["star", "favorite", "rating", "highlight", "special"] },
  { slug: "sparkles", char: "✨", category: "emotion", keywords: ["sparkles", "magic", "magical", "shine", "new", "fresh"] },
  { slug: "party", char: "🎉", category: "emotion", keywords: ["party", "celebrate", "celebration", "congrats", "launch_party"] },
  { slug: "muscle", char: "💪", category: "power", keywords: ["muscle", "strong", "strength", "powerful", "hustle", "grind", "effort", "hard_work"] },
  { slug: "zap", char: "⚡", category: "power", keywords: ["zap", "fast", "quick", "quickly", "instantly", "energy", "speed", "power"] },
  { slug: "boom", char: "💥", category: "power", keywords: ["boom", "explode", "explosion", "impact", "blow_up", "smash"] },
  { slug: "stop_hand", char: "✋", category: "power", keywords: ["stop_hand", "stop", "halt", "wait", "pause", "hold_on"] },
  { slug: "warning", char: "⚠️", category: "power", keywords: ["warning", "danger", "caution", "risk", "careful", "beware"] },
  { slug: "bomb", char: "💣", category: "power", keywords: ["bomb", "ticking", "blow_up_soon", "dangerous", "threat"] },
  { slug: "fist", char: "👊", category: "power", keywords: ["fist", "punch", "hit", "fight", "force"] },
  { slug: "shield", char: "🛡️", category: "power", keywords: ["shield", "protect", "protection", "defense", "safe", "secure"] },
  { slug: "lock", char: "🔒", category: "power", keywords: ["lock", "locked", "private", "closed", "restricted"] },
  { slug: "unlock", char: "🔓", category: "power", keywords: ["unlock", "unlocked", "open_access", "revealed"] },
  { slug: "crown", char: "👑", category: "power", keywords: ["crown", "king", "queen", "royal", "elite", "best_in_class"] },
  { slug: "handshake", char: "🤝", category: "power", keywords: ["handshake", "deal", "agreement", "partner", "team", "secret", "trust"] },
  { slug: "alarm", char: "⏰", category: "time", keywords: ["alarm", "now", "time", "urgent", "hour", "hours", "wake_up"] },
  { slug: "stopwatch", char: "⏱️", category: "time", keywords: ["stopwatch", "minute", "minutes", "second", "seconds", "timer"] },
  { slug: "hourglass", char: "⏳", category: "time", keywords: ["hourglass", "deadline", "running_out", "waiting", "limited_time"] },
  { slug: "calendar", char: "📅", category: "time", keywords: ["calendar", "today", "tomorrow", "day", "days", "date", "schedule"] },
  { slug: "calendar_year", char: "📆", category: "time", keywords: ["calendar_year", "year", "years", "month", "months", "annual"] },
  { slug: "crystal_ball", char: "🔮", category: "time", keywords: ["crystal_ball", "future", "predict", "prediction", "forecast"] },
  { slug: "infinity", char: "♾️", category: "time", keywords: ["infinity", "forever", "unlimited", "endless", "always"] },
  { slug: "repeat", char: "🔁", category: "time", keywords: ["repeat", "loop", "routine", "habit"] },
  { slug: "point_right", char: "👉", category: "people", keywords: ["point_right", "you", "look_here", "listen"] },
  { slug: "eyes", char: "👀", category: "people", keywords: ["eyes", "watch", "watching", "audience", "attention"] },
  { slug: "people", char: "👫", category: "people", keywords: ["people", "everyone", "everybody", "crowd", "public"] },
  { slug: "family", char: "👨‍👩‍👧", category: "people", keywords: ["family", "kids", "children", "parents", "home_life"] },
  { slug: "baby", char: "👶", category: "people", keywords: ["baby", "child", "newborn", "beginner", "infant"] },
  { slug: "briefcase", char: "💼", category: "people", keywords: ["briefcase", "work", "working", "job", "business", "career", "boss"] },
  { slug: "office", char: "🏢", category: "people", keywords: ["office", "company", "corporate", "enterprise", "firm"] },
  { slug: "bell", char: "🔔", category: "people", keywords: ["bell", "subscribe", "notification", "reminder", "alert_bell"] },
  { slug: "mobile", char: "📲", category: "people", keywords: ["mobile", "followers", "social", "dm", "message", "app"] },
  { slug: "megaphone", char: "📢", category: "people", keywords: ["megaphone", "announce", "shout", "marketing", "promote", "loud"] },
  { slug: "mic", char: "🎤", category: "people", keywords: ["mic", "speak", "speaking", "podcast", "interview", "voice"] },
  { slug: "clapping", char: "👏", category: "people", keywords: ["clapping", "applause", "well_done", "respect", "praise"] },
  { slug: "thumbs_up", char: "👍", category: "people", keywords: ["thumbs_up", "like", "approve"] },
  { slug: "thumbs_down", char: "👎", category: "people", keywords: ["thumbs_down", "dislike", "disapprove", "reject"] },
  { slug: "wave", char: "👋", category: "people", keywords: ["wave", "goodbye", "greeting"] },
  { slug: "pray", char: "🙏", category: "people", keywords: ["pray", "thanks", "grateful", "hope"] },
  { slug: "hammer", char: "🔨", category: "build", keywords: ["hammer", "build", "fix", "repair", "tool"] },
  { slug: "construction", char: "🏗️", category: "build", keywords: ["construction", "building", "under_construction", "developing", "wip"] },
  { slug: "gear", char: "⚙️", category: "build", keywords: ["gear", "system", "process", "settings", "machine", "engine"] },
  { slug: "wrench", char: "🔧", category: "build", keywords: ["wrench", "adjust", "tune", "maintenance", "configure"] },
  { slug: "art", char: "🎨", category: "build", keywords: ["art", "create", "creating", "design", "creative", "paint"] },
  { slug: "brick", char: "🧱", category: "build", keywords: ["brick", "foundation", "block", "base", "structure"] },
  { slug: "package", char: "📦", category: "build", keywords: ["package", "product", "ship", "shipping", "delivery", "box"] },
  { slug: "toolbox", char: "🧰", category: "build", keywords: ["toolbox", "toolkit", "resources", "kit", "equipment"] },
  { slug: "robot", char: "🤖", category: "tech", keywords: ["robot", "ai", "automation", "bot", "machine_learning"] },
  { slug: "laptop", char: "💻", category: "tech", keywords: ["laptop", "computer", "code", "coding", "software", "tech", "technology"] },
  { slug: "phone", char: "📱", category: "tech", keywords: ["phone", "smartphone", "mobile_phone", "device"] },
  { slug: "globe", char: "🌍", category: "tech", keywords: ["globe", "world", "earth", "global", "planet", "international"] },
  { slug: "web", char: "🌐", category: "tech", keywords: ["web", "internet", "online", "website", "network"] },
  { slug: "satellite", char: "📡", category: "tech", keywords: ["satellite", "signal", "broadcast", "transmit", "connection"] },
  { slug: "battery", char: "🔋", category: "tech", keywords: ["battery", "charge", "energy_level", "power_left", "recharge"] },
  { slug: "floppy", char: "💾", category: "tech", keywords: ["floppy", "save_file", "backup", "storage", "old_tech"] },
  { slug: "camera", char: "📷", category: "tech", keywords: ["camera", "photo", "picture", "shoot", "capture"] },
  { slug: "movie", char: "🎬", category: "tech", keywords: ["movie", "video", "film", "scene", "production", "clip"] },
  { slug: "tv", char: "📺", category: "tech", keywords: ["tv", "television", "broadcast_tv", "show", "channel"] },
  { slug: "game", char: "🎮", category: "tech", keywords: ["game", "gaming", "gamer", "controller"] },
  { slug: "music", char: "🎵", category: "tech", keywords: ["music", "song", "sound", "audio", "melody"] },
  { slug: "headphones", char: "🎧", category: "tech", keywords: ["headphones", "listen", "listening", "audio_gear", "podcast_listen"] },
  { slug: "gym", char: "🏋️", category: "life", keywords: ["gym", "workout", "lifting", "training", "exercise"] },
  { slug: "run", char: "🏃", category: "life", keywords: ["run", "running", "sprint", "cardio"] },
  { slug: "food", char: "🍴", category: "life", keywords: ["food", "eat", "eating", "meal", "dinner", "restaurant"] },
  { slug: "apple", char: "🍎", category: "life", keywords: ["apple", "healthy", "nutrition", "diet", "fruit"] },
  { slug: "water", char: "💧", category: "life", keywords: ["water", "hydration", "drink", "liquid", "hydrate"] },
  { slug: "sleep", char: "😴", category: "life", keywords: ["sleep", "sleeping", "rest", "tired", "bed"] },
  { slug: "pill", char: "💊", category: "life", keywords: ["pill", "medicine", "drug", "treatment", "health"] },
  { slug: "hospital", char: "🏥", category: "life", keywords: ["hospital", "doctor", "medical", "clinic", "emergency_room"] },
  { slug: "house", char: "🏠", category: "life", keywords: ["house", "home", "property", "real_estate", "living"] },
  { slug: "car", char: "🚘", category: "life", keywords: ["car", "drive", "driving", "vehicle", "commute"] },
  { slug: "plane", char: "✈️", category: "life", keywords: ["plane", "travel", "flight", "trip", "vacation"] },
  { slug: "sun", char: "☀️", category: "life", keywords: ["sun", "sunny", "morning", "bright", "summer"] },
  { slug: "moon", char: "🌙", category: "life", keywords: ["moon", "night", "evening", "late", "dark"] },
  { slug: "seedling", char: "🌱", category: "life", keywords: ["seedling", "beginning", "small_start", "plant", "nature"] },
  { slug: "tree", char: "🌳", category: "life", keywords: ["tree", "nature", "forest", "long_term", "roots"] },
  { slug: "ocean", char: "🌊", category: "life", keywords: ["ocean", "sea", "wave", "water_big", "deep"] },
  { slug: "mountain", char: "⛰️", category: "life", keywords: ["mountain", "climb", "peak", "challenge", "summit"] },
  { slug: "map", char: "🗺️", category: "life", keywords: ["map", "roadmap", "direction", "journey", "navigate"] },
  { slug: "compass", char: "🧭", category: "life", keywords: ["compass", "guidance", "direction_find", "orientation", "north"] },
  { slug: "flag", char: "🚩", category: "life", keywords: ["flag", "milestone", "marker", "claim", "checkpoint"] },
  { slug: "ticket", char: "🎫", category: "life", keywords: ["ticket", "entry", "pass", "admission", "event"] },
  { slug: "gift", char: "🎁", category: "life", keywords: ["gift", "present", "bonus", "reward", "surprise_gift"] },
  { slug: "ball", char: "⚽", category: "life", keywords: ["ball", "sports", "soccer", "football", "game_sport"] },
];

const BY_SLUG = new Map(EMOJI_CATALOG.map((e) => [e.slug, e]));
const BY_KEYWORD = new Map<string, EmojiCatalogEntry>();
for (const entry of EMOJI_CATALOG) {
  for (const keyword of entry.keywords) {
    if (!BY_KEYWORD.has(keyword)) BY_KEYWORD.set(keyword, entry);
  }
}

export const normalizeEmojiKeyword = (value: string): string =>
  (value || '').toLowerCase().replace(/[^a-z0-9%]+/g, '');

/** Resolve a catalog slug to its emoji, or null when it is not whitelisted. */
export const emojiForSlug = (slug: string): string | null =>
  BY_SLUG.get(slug)?.char ?? null;

/** Resolve a spoken word to its emoji, mirroring the backend keyword map. */
export const emojiForKeyword = (word: string): string | null =>
  BY_KEYWORD.get(normalizeEmojiKeyword(word))?.char ?? null;

export const emojiByCategory = (category: EmojiCategory): EmojiCatalogEntry[] =>
  EMOJI_CATALOG.filter((e) => e.category === category);
