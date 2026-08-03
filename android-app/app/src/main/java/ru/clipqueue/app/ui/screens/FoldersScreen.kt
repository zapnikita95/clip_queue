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
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.components.VideoListRow
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted

@Composable
fun FoldersScreen(
    api: ApiClient,
    onBackHome: () -> Unit,
    onOpenFolder: (ListCard) -> Unit,
    onOpenProfile: () -> Unit,
) {
    var loading by remember { mutableStateOf(true) }
    var folders by remember { mutableStateOf<List<ListCard>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        loading = true
        try {
            folders = api.lists().lists.orEmpty()
        } catch (e: Exception) {
            error = e.message
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
        Text("РџР°РїРєРё", style = MaterialTheme.typography.titleLarge)
        Text("СЂР°Р·Р»РѕР¶РµРЅРѕ РЅР° Р±СЌРєРµ", style = MaterialTheme.typography.bodySmall, color = CqMuted)

        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = CqAccent)
            }
            error != null -> Text(error.orEmpty(), color = CqAccent)
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(folders, key = { it.id ?: 0 }) { folder ->
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(CqElev, RoundedCornerShape(14.dp))
                            .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
                            .clickable { onOpenFolder(folder) }
                            .padding(16.dp),
                    ) {
                        Text(folder.title.orEmpty(), style = MaterialTheme.typography.titleMedium)
                        Text(
                            "${folder.count ?: 0} РІРёРґРµРѕ",
                            style = MaterialTheme.typography.bodySmall,
                            color = CqMuted,
                        )
                    }
                }
            }
        }
        BottomBar(selected = 1, onHome = onBackHome, onFolders = {}, onProfile = onOpenProfile)
    }
}

@Composable
fun FolderDetailScreen(
    api: ApiClient,
    folder: ListCard,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var items by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var title by remember { mutableStateOf(folder.title.orEmpty()) }

    LaunchedEffect(folder.id) {
        val id = folder.id ?: return@LaunchedEffect
        loading = true
        try {
            val r = api.listDetail(id)
            title = r.list?.title ?: title
            items = r.items.orEmpty()
        } catch (_: Exception) {
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
        Text(
            "в†ђ РїР°РїРєРё",
            color = CqMuted,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.clickable(onClick = onBack),
        )
        Spacer(Modifier.height(6.dp))
        Text(title, style = MaterialTheme.typography.titleLarge)

        if (loading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = CqAccent)
            }
        } else {
            LazyColumn(modifier = Modifier.weight(1f)) {
                items(items, key = { it.video_id.orEmpty() }) { card ->
                    VideoListRow(card) {
                        scope.launch {
                            val id = card.video_id ?: return@launch
                            val watch = runCatching { api.openVideo(id).watch_url }.getOrNull()
                                ?: card.watch_url
                                ?: "https://www.youtube.com/watch?v=$id"
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(watch)))
                        }
                    }
                }
            }
        }
    }
}
