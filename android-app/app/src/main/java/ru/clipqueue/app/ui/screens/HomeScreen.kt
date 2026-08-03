package ru.clipqueue.app.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.components.SectionLabel
import ru.clipqueue.app.ui.components.VideoRail
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted

@Composable
fun HomeScreen(
    api: ApiClient,
    onOpenFolder: (ListCard) -> Unit,
    onOpenFolders: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var recent by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var vibe by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var fromPlaylists by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var folders by remember { mutableStateOf<List<ListCard>>(emptyList()) }

    suspend fun openVideo(card: VideoCard) {
        val id = card.video_id ?: return
        val watch = try {
            api.openVideo(id).watch_url
        } catch (_: Exception) {
            null
        } ?: card.watch_url ?: "https://www.youtube.com/watch?v=$id"
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(watch)))
    }

    LaunchedEffect(Unit) {
        loading = true
        error = null
        try {
            // Fire-and-forget playlist sync on entry
            launch {
                runCatching { api.startYoutubeSync(full = false) }
            }
            coroutineScope {
                val recentDef = async { api.homeRail("queue") }
                val vibeDef = async { api.homeRail("continue_vibe") }
                val plDef = async { api.homeRail("from_playlists") }
                val listsDef = async { api.lists() }
                recent = recentDef.await().items.orEmpty()
                vibe = vibeDef.await().items.orEmpty()
                fromPlaylists = plDef.await().items.orEmpty()
                folders = listsDef.await().lists.orEmpty().take(6)
            }
        } catch (e: Exception) {
            error = e.message ?: "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ"
        } finally {
            loading = false
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CqBg)
            .padding(horizontal = 20.dp),
    ) {
        Spacer(Modifier.height(18.dp))
        Text("Clip Queue", style = MaterialTheme.typography.titleLarge)
        Text("РёР· С‚РІРѕРµРіРѕ В· РЅРµ Р»РµРЅС‚Р° YouTube", style = MaterialTheme.typography.bodySmall, color = CqMuted)

        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = CqAccent)
            }
            error != null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(error.orEmpty(), color = CqAccent)
            }
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(bottom = 12.dp),
            ) {
                item {
                    SectionLabel("РќРµРґР°РІРЅРѕ РґРѕР±Р°РІР»РµРЅРЅС‹Рµ")
                    if (recent.isEmpty()) {
                        Text("РџРѕРєР° РїСѓСЃС‚Рѕ вЂ” РїРѕРґРµР»РёСЃСЊ СЂРѕР»РёРєРѕРј РёР· YouTube", color = CqMuted)
                    } else {
                        VideoRail(recent) { scope.launch { openVideo(it) } }
                    }
                }
                item {
                    SectionLabel("РњРѕРіСѓС‚ РїРѕРЅСЂР°РІРёС‚СЊСЃСЏ")
                    val recs = if (vibe.isNotEmpty()) vibe else fromPlaylists
                    if (recs.isEmpty()) {
                        Text("РЎРјРѕС‚СЂРё СЂРѕР»РёРєРё вЂ” РїРѕРґС‚СЏРЅРµРј РІР°Р№Р±", color = CqMuted)
                    } else {
                        VideoRail(recs) { scope.launch { openVideo(it) } }
                    }
                }
                if (fromPlaylists.isNotEmpty() && vibe.isNotEmpty()) {
                    item {
                        SectionLabel("РР· РїР»РµР№Р»РёСЃС‚РѕРІ")
                        VideoRail(fromPlaylists) { scope.launch { openVideo(it) } }
                    }
                }
                item {
                    SectionLabel("РџР°РїРєРё")
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        folders.take(4).forEach { folder ->
                            Column(
                                modifier = Modifier
                                    .weight(1f)
                                    .background(CqElev, RoundedCornerShape(12.dp))
                                    .border(1.dp, CqBorder, RoundedCornerShape(12.dp))
                                    .clickable { onOpenFolder(folder) }
                                    .padding(12.dp),
                            ) {
                                Text(
                                    folder.title.orEmpty(),
                                    style = MaterialTheme.typography.titleMedium,
                                    maxLines = 1,
                                )
                                Text(
                                    "${folder.count ?: 0} РІРёРґРµРѕ",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = CqMuted,
                                )
                            }
                        }
                    }
                    if (folders.isEmpty()) {
                        Text("РџР°РїРєРё РїРѕСЏРІСЏС‚СЃСЏ РїРѕСЃР»Рµ organize / share", color = CqMuted)
                    }
                }
            }
        }

        BottomBar(selected = 0, onHome = {}, onFolders = onOpenFolders, onProfile = onOpenProfile)
    }
}

@Composable
fun BottomBar(
    selected: Int,
    onHome: () -> Unit,
    onFolders: () -> Unit,
    onProfile: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 14.dp),
        horizontalArrangement = Arrangement.SpaceAround,
    ) {
        listOf(
            Triple(0, "Р›РµРЅС‚Р°", onHome),
            Triple(1, "РџР°РїРєРё", onFolders),
            Triple(2, "РџСЂРѕС„РёР»СЊ", onProfile),
        ).forEach { (idx, label, action) ->
            Text(
                text = label,
                color = if (selected == idx) CqAccent else CqMuted,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.clickable(onClick = action),
            )
        }
    }
}
