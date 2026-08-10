package ru.clipqueue.app.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import coil.compose.AsyncImage
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqElev2
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText

private val TrashRed = Color(0xFFE53935)
private val TrashRedDark = Color(0xFFB71C1C)

/**
 * Floating trash for folder edit mode — always clearly red; grows when a tile is over it.
 */
@Composable
fun FolderTrashZone(
    editing: Boolean,
    hot: Boolean,
    onBounds: (Rect) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (!editing) return
    Column(
        modifier = modifier
            .onGloballyPositioned { onBounds(it.boundsInRoot()) }
            .zIndex(40f),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            modifier = Modifier
                .size(if (hot) 72.dp else 64.dp)
                .clip(CircleShape)
                .background(if (hot) TrashRedDark else TrashRed)
                .border(2.dp, Color.White.copy(alpha = 0.85f), CircleShape)
                .graphicsLayer {
                    scaleX = if (hot) 1.08f else 1f
                    scaleY = if (hot) 1.08f else 1f
                },
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                Icons.Default.Delete,
                contentDescription = "Удалить папку",
                tint = Color.White,
                modifier = Modifier.size(if (hot) 34.dp else 30.dp),
            )
        }
        Spacer(Modifier.height(4.dp))
        Text(
            if (hot) "Отпустите" else "На корзину",
            color = TrashRed,
            style = MaterialTheme.typography.labelMedium,
        )
    }
}

@Composable
fun EditableFolderGrid(
    folders: List<ListCard>,
    editing: Boolean,
    trashBounds: Rect?,
    onOpenFolder: (ListCard) -> Unit,
    onEnterEdit: () -> Unit,
    onDragHotChange: (Boolean) -> Unit,
    onDropOnTrash: (ListCard) -> Unit,
    onReorder: (List<ListCard>) -> Unit,
    modifier: Modifier = Modifier,
) {
    val cellBounds = remember { mutableStateMapOf<Int, Rect>() }

    fun indexAt(point: Offset): Int? {
        // Prefer containing cell; else nearest center
        val containing = cellBounds.entries.filter { it.value.contains(point) }
        if (containing.isNotEmpty()) {
            return containing.minByOrNull { (it.value.center - point).getDistance() }?.key
        }
        return cellBounds.minByOrNull { (it.value.center - point).getDistance() }?.key
    }

    Column(
        modifier = modifier.fillMaxWidth().padding(horizontal = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        folders.chunked(2).forEachIndexed { rowIdx, row ->
            Row(
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.fillMaxWidth().height(IntrinsicSize.Min),
            ) {
                row.forEachIndexed { colIdx, folder ->
                    val index = rowIdx * 2 + colIdx
                    EditableFolderCell(
                        folder = folder,
                        editing = editing,
                        trashBounds = trashBounds,
                        onOpenFolder = onOpenFolder,
                        onEnterEdit = onEnterEdit,
                        onBounds = { cellBounds[index] = it },
                        onDragHotChange = onDragHotChange,
                        onDropOnTrash = onDropOnTrash,
                        onDragEndAt = { center ->
                            val hot = trashBounds?.contains(center) == true
                            onDragHotChange(false)
                            if (hot) {
                                onDropOnTrash(folder)
                                return@EditableFolderCell
                            }
                            val to = indexAt(center) ?: return@EditableFolderCell
                            val from = folders.indexOfFirst { it.id == folder.id }
                            if (from < 0 || from == to) return@EditableFolderCell
                            val next = folders.toMutableList()
                            val item = next.removeAt(from)
                            next.add(to.coerceIn(0, next.size), item)
                            onReorder(next)
                        },
                        modifier = Modifier.weight(1f).fillMaxHeight(),
                    )
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun EditableFolderCell(
    folder: ListCard,
    editing: Boolean,
    trashBounds: Rect?,
    onOpenFolder: (ListCard) -> Unit,
    onEnterEdit: () -> Unit,
    onBounds: (Rect) -> Unit,
    onDragHotChange: (Boolean) -> Unit,
    onDropOnTrash: (ListCard) -> Unit,
    onDragEndAt: (Offset) -> Unit,
    modifier: Modifier,
) {
    val haptics = LocalHapticFeedback.current
    var dragging by remember { mutableStateOf(false) }
    var drag by remember { mutableStateOf(Offset.Zero) }
    var cellBounds by remember { mutableStateOf(Rect.Zero) }

    val jiggle = if (editing && !dragging) {
        val t = rememberInfiniteTransition(label = "jiggle")
        val phase = ((folder.id ?: 0) % 5) * 40
        t.animateFloat(
            initialValue = -2.2f,
            targetValue = 2.2f,
            animationSpec = infiniteRepeatable(
                animation = tween(120 + phase, easing = LinearEasing),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "rot",
        ).value
    } else {
        0f
    }

    Box(
        modifier = modifier
            .zIndex(if (dragging) 8f else 0f)
            .onGloballyPositioned {
                cellBounds = it.boundsInRoot()
                onBounds(cellBounds)
            }
            .graphicsLayer {
                rotationZ = jiggle
                translationX = drag.x
                translationY = drag.y
                scaleX = if (dragging) 1.05f else 1f
                scaleY = if (dragging) 1.05f else 1f
                alpha = if (dragging) 0.92f else 1f
            }
            .pointerInput(editing, folder.id, trashBounds) {
                detectDragGesturesAfterLongPress(
                    onDragStart = {
                        haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                        onEnterEdit()
                        dragging = true
                        drag = Offset.Zero
                    },
                    onDrag = { change, amount ->
                        change.consume()
                        drag += amount
                        val center = cellBounds.center + drag
                        onDragHotChange(trashBounds?.contains(center) == true)
                    },
                    onDragEnd = {
                        val center = cellBounds.center + drag
                        dragging = false
                        drag = Offset.Zero
                        onDragEndAt(center)
                    },
                    onDragCancel = {
                        dragging = false
                        drag = Offset.Zero
                        onDragHotChange(false)
                    },
                )
            }
            .clip(RoundedCornerShape(14.dp))
            .background(CqElev)
            .border(1.dp, if (dragging) CqAccent else CqBorder, RoundedCornerShape(14.dp))
            .clickable(enabled = !editing) { onOpenFolder(folder) }
            .padding(10.dp),
    ) {
        Column {
            Row(horizontalArrangement = Arrangement.spacedBy(3.dp), modifier = Modifier.fillMaxWidth()) {
                val covers = folder.covers.orEmpty().take(3)
                if (covers.isEmpty()) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(56.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(CqElev2),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Default.Folder, null, tint = CqMuted, modifier = Modifier.size(22.dp))
                    }
                } else {
                    covers.forEach { c ->
                        AsyncImage(
                            model = c.thumb_url,
                            contentDescription = null,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier
                                .weight(1f)
                                .height(56.dp)
                                .clip(RoundedCornerShape(6.dp)),
                        )
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
            Text(
                folder.title.orEmpty(),
                style = MaterialTheme.typography.titleMedium,
                maxLines = 2,
                minLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.height(44.dp),
            )
            Text("${folder.count ?: 0} видео", color = CqMuted, style = MaterialTheme.typography.bodySmall)
        }
        if (editing) {
            Box(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .size(22.dp)
                    .clip(CircleShape)
                    .background(CqAccent)
                    .clickable { onDropOnTrash(folder) },
                contentAlignment = Alignment.Center,
            ) {
                Text("×", color = CqText, style = MaterialTheme.typography.titleMedium)
            }
        }
    }
}

@Composable
fun FolderRemoveDialog(
    folder: ListCard,
    onDismiss: () -> Unit,
    onHideFromHome: () -> Unit,
    onDeleteEverywhere: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(folder.title.orEmpty().ifBlank { "Папка" }) },
        text = null,
        confirmButton = {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TextButton(onClick = onHideFromHome) { Text("С главной") }
                TextButton(onClick = onDeleteEverywhere) {
                    Text("Удалить совсем", color = CqAccent)
                }
                TextButton(onClick = onDismiss) { Text("Отмена") }
            }
        },
        dismissButton = {},
    )
}
