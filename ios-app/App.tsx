import { StatusBar } from "expo-status-bar";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  Linking as RNLinking,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  VideoCard,
  ListCard,
  api,
  apiBase,
  getToken,
  setToken,
} from "./src/api";

WebBrowser.maybeCompleteAuthSession();

type Tab = "now" | "folders" | "save";

export default function App() {
  const [token, setTok] = useState<string | null>(null);
  const [booting, setBooting] = useState(true);
  const [tab, setTab] = useState<Tab>("now");
  const [loginBusy, setLoginBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      const t = await getToken();
      setTok(t || null);
      setBooting(false);
    })();
  }, []);

  useEffect(() => {
    const onUrl = ({ url }: { url: string }) => {
      const parsed = Linking.parse(url);
      const t = (parsed.queryParams?.token as string) || "";
      if (t) {
        setToken(t).then(() => setTok(t));
      }
      const shared = (parsed.queryParams?.url as string) || "";
      if (shared && /youtu/.test(shared)) {
        setTab("save");
        void saveUrl(shared);
      }
    };
    const sub = Linking.addEventListener("url", onUrl);
    Linking.getInitialURL().then((u) => {
      if (u) onUrl({ url: u });
    });
    return () => sub.remove();
  }, []);

  const googleLogin = async () => {
    setLoginBusy(true);
    setErr("");
    try {
      const start = `${apiBase()}/api/auth/google/start?client=ios&redirect=${encodeURIComponent("kyro://auth")}`;
      await WebBrowser.openAuthSessionAsync(start, "kyro://auth");
      // token usually arrives via deep link listener
    } catch (e: any) {
      setErr(e.message || "Не удалось войти");
    } finally {
      setLoginBusy(false);
    }
  };

  const saveUrl = async (url: string) => {
    await api("/api/videos/save", {
      method: "POST",
      body: {
        url,
        source: "ios_share",
        apply_classification: true,
        classify_async: true,
        status: "queue",
      },
    });
  };

  if (booting) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#e85d4c" />
      </View>
    );
  }

  if (!token) {
    return (
      <SafeAreaView style={styles.root}>
        <View style={styles.pad}>
          <Text style={styles.brand}>Kyro</Text>
          <Text style={styles.sub}>
            Сохраняйте YouTube и понимайте, что смотреть сейчас — из вашего желаемого.
          </Text>
          <Pressable style={styles.btn} onPress={googleLogin} disabled={loginBusy}>
            <Text style={styles.btnText}>{loginBusy ? "…" : "Войти через Google"}</Text>
          </Pressable>
          {!!err && <Text style={styles.err}>{err}</Text>}
          <Text style={styles.hint}>
            Если deep link не сработал: откройте кабинет в Safari, скопируйте токен и вставьте ниже.
          </Text>
          <TextInput
            style={styles.input}
            placeholder="cq_session_token"
            placeholderTextColor="#666"
            autoCapitalize="none"
            onSubmitEditing={async (e) => {
              const v = e.nativeEvent.text.trim();
              if (!v) return;
              await setToken(v);
              setTok(v);
            }}
          />
        </View>
        <StatusBar style="light" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.top}>
        <Text style={styles.brandSm}>Kyro</Text>
        <Pressable
          onPress={async () => {
            await setToken("");
            setTok(null);
          }}
        >
          <Text style={styles.link}>Выйти</Text>
        </Pressable>
      </View>
      <View style={styles.body}>
        {tab === "now" && <NowTab />}
        {tab === "folders" && <FoldersTab />}
        {tab === "save" && <SaveTab onSaved={() => setTab("now")} />}
      </View>
      <View style={styles.tabBar}>
        {(
          [
            ["now", "Сейчас"],
            ["folders", "Папки"],
            ["save", "Сохранить"],
          ] as const
        ).map(([id, label]) => (
          <Pressable key={id} style={styles.tabBtn} onPress={() => setTab(id)}>
            <Text style={[styles.tabLabel, tab === id && styles.tabActive]}>{label}</Text>
          </Pressable>
        ))}
      </View>
      <StatusBar style="light" />
    </SafeAreaView>
  );
}

function NowTab() {
  const [slot, setSlot] = useState("any");
  const [mood, setMood] = useState("");
  const [picks, setPicks] = useState<VideoCard[]>([]);
  const [suggestions, setSuggestions] = useState<VideoCard[]>([]);
  const [slots, setSlots] = useState<{ id: string; label: string }[]>([]);
  const [moods, setMoods] = useState<{ id: string; label: string }[]>([]);
  const [plan, setPlan] = useState<VideoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [meta, setMeta] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams({ slot, limit: "6" });
      if (mood) qs.set("mood", mood);
      const data = await api(`/api/home/now?${qs}`);
      const started = data.started || [];
      const p = data.picks || [];
      const seen = new Set(p.map((x: VideoCard) => x.video_id));
      setPicks([...started.filter((s: VideoCard) => !seen.has(s.video_id)), ...p]);
      setSuggestions(data.suggestions || []);
      if (data.slots?.length) setSlots(data.slots);
      if (data.moods?.length) setMoods(data.moods);
      setMeta(data.slot_label || "");
      await api("/api/metrics/track", {
        method: "POST",
        body: { event_type: "now_impression", surface: "ios_home" },
      }).catch(() => {});
      const pl = await api("/api/home/plan");
      setPlan(pl.tonight || []);
    } catch (_) {
      setPicks([]);
    } finally {
      setLoading(false);
    }
  }, [slot, mood]);

  useEffect(() => {
    load();
  }, [load]);

  const open = async (item: VideoCard, surface: string) => {
    try {
      const r = await api(`/api/videos/${encodeURIComponent(item.video_id)}/open`, {
        method: "POST",
        body: { surface },
      });
      const url = r.watch_url || item.watch_url || `https://www.youtube.com/watch?v=${item.video_id}`;
      await RNLinking.openURL(url);
    } catch (_) {
      await RNLinking.openURL(item.watch_url || `https://www.youtube.com/watch?v=${item.video_id}`);
    }
  };

  if (loading && !picks.length) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#e85d4c" />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.pad}>
      <Text style={styles.h1}>Сейчас</Text>
      {!!meta && <Text style={styles.sub}>{meta}</Text>}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chips}>
        {slots.map((s) => (
          <Pressable
            key={s.id}
            style={[styles.chip, slot === s.id && styles.chipOn]}
            onPress={() => setSlot(s.id)}
          >
            <Text style={styles.chipText}>{s.label}</Text>
          </Pressable>
        ))}
      </ScrollView>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chips}>
        <Pressable
          style={[styles.chip, !mood && styles.chipOn]}
          onPress={() => setMood("")}
        >
          <Text style={styles.chipText}>Все</Text>
        </Pressable>
        {moods.map((m) => (
          <Pressable
            key={m.id}
            style={[styles.chip, mood === m.id && styles.chipOn]}
            onPress={() => setMood(m.id)}
          >
            <Text style={styles.chipText}>{m.label}</Text>
          </Pressable>
        ))}
      </ScrollView>
      {picks.map((it) => (
        <VideoRow key={it.video_id} item={it} onPress={() => open(it, "now")} />
      ))}
      {!!suggestions.length && (
        <>
          <Text style={styles.h2}>Можно посмотреть</Text>
          {suggestions.map((it) => (
            <VideoRow key={it.video_id} item={it} onPress={() => open(it, "suggestion")} />
          ))}
        </>
      )}
      <Text style={styles.h2}>План на вечер</Text>
      {!plan.length && <Text style={styles.sub}>Пока пусто — добавьте из веба или Android</Text>}
      {plan.map((it) => (
        <VideoRow key={it.video_id} item={it} onPress={() => open(it, "plan_tonight")} />
      ))}
      <Pressable onPress={() => RNLinking.openURL("https://movie-planner.ru/?open_login=1")}>
        <Text style={[styles.link, { marginTop: 16 }]}>Кино — Movie Planner</Text>
      </Pressable>
    </ScrollView>
  );
}

function FoldersTab() {
  const [lists, setLists] = useState<ListCard[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await api("/api/lists?for_home=1");
        setLists(r.lists || []);
      } catch (_) {
        setLists([]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#e85d4c" />
      </View>
    );
  }

  return (
    <FlatList
      contentContainerStyle={styles.pad}
      data={lists}
      keyExtractor={(i) => String(i.id)}
      ListHeaderComponent={<Text style={styles.h1}>Папки</Text>}
      renderItem={({ item }) => (
        <View style={styles.folder}>
          <Text style={styles.folderTitle}>{item.title}</Text>
          <Text style={styles.sub}>{item.count ?? 0}</Text>
        </View>
      )}
      ListEmptyComponent={<Text style={styles.sub}>Папок пока нет — синхронизируйте YouTube в вебе</Text>}
    />
  );
}

function SaveTab({ onSaved }: { onSaved: () => void }) {
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    setMsg("");
    try {
      await api("/api/videos/save", {
        method: "POST",
        body: {
          url,
          source: "ios_share",
          apply_classification: true,
          classify_async: true,
          status: "queue",
        },
      });
      setMsg("Сохранено в Kyro");
      setUrl("");
      onSaved();
    } catch (e: any) {
      setMsg(e.message || "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.pad}>
      <Text style={styles.h1}>Сохранить</Text>
      <Text style={styles.sub}>
        Share Extension (Xcode target) шлёт ссылку сюда. Пока можно вставить URL вручную.
      </Text>
      <TextInput
        style={styles.input}
        placeholder="https://youtu.be/…"
        placeholderTextColor="#666"
        autoCapitalize="none"
        value={url}
        onChangeText={setUrl}
      />
      <Pressable style={styles.btn} onPress={save} disabled={busy || !url.trim()}>
        <Text style={styles.btnText}>{busy ? "…" : "В Kyro"}</Text>
      </Pressable>
      {!!msg && <Text style={styles.sub}>{msg}</Text>}
    </View>
  );
}

function VideoRow({ item, onPress }: { item: VideoCard; onPress: () => void }) {
  return (
    <Pressable style={styles.card} onPress={onPress}>
      {!!item.thumb_url && <Image source={{ uri: item.thumb_url }} style={styles.thumb} />}
      <View style={{ flex: 1 }}>
        {!!item.reason && <Text style={styles.reason}>{item.reason}</Text>}
        <Text style={styles.title} numberOfLines={2}>
          {item.title || item.video_id}
        </Text>
        <Text style={styles.sub} numberOfLines={1}>
          {item.channel_title || ""}
          {item.duration_label ? ` · ${item.duration_label}` : ""}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0a0a0c" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#0a0a0c" },
  pad: { padding: 16, paddingBottom: 40 },
  brand: { fontSize: 36, color: "#fff", fontWeight: "600", marginBottom: 10 },
  brandSm: { fontSize: 20, color: "#fff", fontWeight: "600" },
  h1: { fontSize: 24, color: "#fff", fontWeight: "600", marginBottom: 8 },
  h2: { fontSize: 18, color: "#fff", fontWeight: "500", marginTop: 18, marginBottom: 8 },
  sub: { color: "#9a9aa0", fontSize: 14, marginBottom: 8 },
  btn: {
    backgroundColor: "#e85d4c",
    padding: 14,
    borderRadius: 12,
    alignItems: "center",
    marginTop: 12,
  },
  btnText: { color: "#fff", fontWeight: "600" },
  input: {
    borderWidth: 1,
    borderColor: "#333",
    borderRadius: 10,
    padding: 12,
    color: "#fff",
    marginTop: 12,
  },
  err: { color: "#e85d4c", marginTop: 10 },
  hint: { color: "#666", fontSize: 12, marginTop: 16 },
  top: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#222",
  },
  body: { flex: 1 },
  tabBar: {
    flexDirection: "row",
    borderTopWidth: 1,
    borderTopColor: "#222",
    paddingVertical: 10,
  },
  tabBtn: { flex: 1, alignItems: "center" },
  tabLabel: { color: "#777", fontSize: 13 },
  tabActive: { color: "#e85d4c", fontWeight: "600" },
  link: { color: "#e85d4c", fontSize: 13 },
  chips: { marginBottom: 10, maxHeight: 40 },
  chip: {
    borderWidth: 1,
    borderColor: "#333",
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginRight: 8,
  },
  chipOn: { backgroundColor: "#e85d4c", borderColor: "#e85d4c" },
  chipText: { color: "#fff", fontSize: 12 },
  card: {
    flexDirection: "row",
    gap: 10,
    marginBottom: 12,
    backgroundColor: "#141418",
    borderRadius: 12,
    padding: 8,
  },
  thumb: { width: 120, height: 68, borderRadius: 8, backgroundColor: "#222" },
  title: { color: "#fff", fontSize: 14, fontWeight: "500" },
  reason: { color: "#9a9aa0", fontSize: 11, marginBottom: 2 },
  folder: {
    padding: 14,
    borderRadius: 12,
    backgroundColor: "#141418",
    marginBottom: 8,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  folderTitle: { color: "#fff", fontSize: 15 },
});
