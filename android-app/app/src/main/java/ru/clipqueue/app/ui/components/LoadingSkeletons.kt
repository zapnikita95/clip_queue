package ru.clipqueue.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import ru.clipqueue.app.ui.theme.CqElev2

@Composable
private fun SkeletonBlock(modifier: Modifier) {
    Box(modifier.clip(RoundedCornerShape(10.dp)).background(CqElev2))
}

@Composable
fun HomePageSkeleton(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.verticalScroll(rememberScrollState()).padding(vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(22.dp),
    ) {
        repeat(4) {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                SkeletonBlock(Modifier.padding(horizontal = 12.dp).width(116.dp).height(18.dp))
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    repeat(3) {
                        Column(modifier = Modifier.width(164.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                            SkeletonBlock(Modifier.fillMaxWidth().aspectRatio(16f / 9f))
                            SkeletonBlock(Modifier.fillMaxWidth(0.88f).height(13.dp))
                            SkeletonBlock(Modifier.fillMaxWidth(0.58f).height(10.dp))
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun VideoListSkeleton(modifier: Modifier = Modifier, rows: Int = 5) {
    Column(
        modifier = modifier.verticalScroll(rememberScrollState()).padding(horizontal = 10.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        repeat(rows) {
            Row(
                modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(CqElev2).padding(8.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                SkeletonBlock(Modifier.width(120.dp).aspectRatio(16f / 9f))
                Column(modifier = Modifier.weight(1f).padding(top = 4.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SkeletonBlock(Modifier.fillMaxWidth(0.92f).height(14.dp))
                    SkeletonBlock(Modifier.fillMaxWidth(0.72f).height(14.dp))
                    Spacer(Modifier.size(2.dp))
                    SkeletonBlock(Modifier.fillMaxWidth(0.48f).height(10.dp))
                }
            }
        }
    }
}

@Composable
fun FolderGridSkeleton(modifier: Modifier = Modifier, rows: Int = 4) {
    Column(
        modifier = modifier.verticalScroll(rememberScrollState()).padding(horizontal = 12.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        repeat(rows) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                repeat(2) {
                    Column(
                        modifier = Modifier.weight(1f).clip(RoundedCornerShape(14.dp)).background(CqElev2).padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        SkeletonBlock(Modifier.fillMaxWidth().height(82.dp))
                        SkeletonBlock(Modifier.fillMaxWidth(0.78f).height(14.dp))
                        SkeletonBlock(Modifier.fillMaxWidth(0.42f).height(10.dp))
                    }
                }
            }
        }
    }
}

@Composable
fun TodayPageSkeleton(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.verticalScroll(rememberScrollState()).padding(vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        repeat(2) {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                SkeletonBlock(Modifier.padding(horizontal = 16.dp).width(132.dp).height(18.dp))
                repeat(2) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp).clip(RoundedCornerShape(14.dp))
                            .background(CqElev2).padding(8.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        SkeletonBlock(Modifier.width(112.dp).aspectRatio(16f / 9f))
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            SkeletonBlock(Modifier.fillMaxWidth(0.9f).height(14.dp))
                            SkeletonBlock(Modifier.fillMaxWidth(0.64f).height(12.dp))
                            SkeletonBlock(Modifier.width(76.dp).height(26.dp))
                        }
                    }
                }
            }
        }
    }
}
