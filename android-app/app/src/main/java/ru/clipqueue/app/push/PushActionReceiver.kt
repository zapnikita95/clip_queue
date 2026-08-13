package ru.clipqueue.app.push

import android.app.Application
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.core.app.NotificationManagerCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import ru.clipqueue.app.ClipQueueApp
import ru.clipqueue.app.MainActivity
import ru.clipqueue.app.clipQueue

/** Handles notification action buttons without requiring a full UI navigation. */
class PushActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent == null) return
        val videoId = sequenceOf(
            intent.getStringExtra(MainActivity.EXTRA_VIDEO_ID),
            intent.getStringExtra("video_id"),
        ).mapNotNull { it?.trim()?.takeIf { s -> s.isNotBlank() } }.firstOrNull().orEmpty()
        val surface = intent.getStringExtra("surface")?.trim().orEmpty().ifBlank { "morning" }
        val notifId = intent.getIntExtra(EXTRA_NOTIF_ID, 0)

        when (intent.action) {
            ACTION_NOT_INTERESTED -> {
                if (videoId.isBlank()) return
                if (notifId != 0) {
                    runCatching { NotificationManagerCompat.from(context).cancel(notifId) }
                }
                val pending = goAsync()
                val app = (context.applicationContext as Application).clipQueue()
                scope.launch {
                    try {
                        if (app.session.isLoggedIn) {
                            runCatching {
                                app.api.pushFeedback(
                                    videoId = videoId,
                                    action = "not_interested",
                                    surface = surface,
                                )
                            }
                            runCatching { app.api.setInterest(videoId, -1) }
                        }
                        Toast.makeText(
                            context.applicationContext,
                            "Ок — таких утром будет меньше",
                            Toast.LENGTH_SHORT,
                        ).show()
                    } finally {
                        pending.finish()
                    }
                }
            }
        }
    }

    companion object {
        const val ACTION_NOT_INTERESTED = "ru.clipqueue.app.PUSH_NOT_INTERESTED"
        const val EXTRA_NOTIF_ID = "kyro_notif_id"
        private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    }
}
