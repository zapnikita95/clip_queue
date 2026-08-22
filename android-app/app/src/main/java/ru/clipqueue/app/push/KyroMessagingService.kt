package ru.clipqueue.app.push

import android.app.PendingIntent
import android.content.Intent
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import ru.clipqueue.app.MainActivity
import ru.clipqueue.app.R

/**
 * Builds local notifications from data-only FCM so:
 * - tap always opens clipqueue://video/{id} in MainActivity
 * - action buttons work (system tray FCM notification payload cannot add them reliably)
 */
class KyroMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        super.onNewToken(token)
        PushRegistrar.onNewToken(applicationContext, token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val payload = message.data
        val videoId = payload["video_id"].orEmpty().trim()
        val pushType = payload["type"].orEmpty().trim().lowercase()
        val headline = sequenceOf(
            payload["title"],
            message.notification?.title,
        ).mapNotNull { it?.trim()?.takeIf { s -> s.isNotBlank() } }
            .firstOrNull()
            ?: defaultHeadline(pushType)
        val body = sequenceOf(
            payload["body"],
            payload["video_title"],
            message.notification?.body,
        ).mapNotNull { it?.trim()?.takeIf { s -> s.isNotBlank() } }
            .firstOrNull()
            ?: getString(R.string.notif_default_body)
        val surface = pushType.ifBlank { "push" }
        val notifId = (videoId.ifBlank { "$headline$body" }).hashCode()

        PushRegistrar.ensureChannel(this)

        val openPi = activityPi(
            requestCode = notifId,
            videoId = videoId,
            surface = surface,
            cta = "open",
        )
        val builder = NotificationCompat.Builder(this, PushRegistrar.CHANNEL_CLASSIFY)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(headline)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(openPi)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_RECOMMENDATION)

        if (videoId.isNotBlank()) {
            builder.addAction(
                0,
                "Открыть",
                activityPi(notifId + 21, videoId, surface, cta = "open"),
            )
            builder.addAction(
                0,
                "Неинтересно",
                broadcastPi(notifId + 22, videoId, surface, PushActionReceiver.ACTION_NOT_INTERESTED, notifId),
            )
        }

        try {
            NotificationManagerCompat.from(this).notify(notifId, builder.build())
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS not granted
        }
    }

    private fun activityPi(
        requestCode: Int,
        videoId: String,
        surface: String,
        cta: String,
    ): PendingIntent {
        val open = Intent(this, MainActivity::class.java).apply {
            action = Intent.ACTION_VIEW
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            if (videoId.isNotBlank()) {
                data = Uri.parse("clipqueue://video/$videoId?surface=$surface&action=$cta")
                putExtra(MainActivity.EXTRA_VIDEO_ID, videoId)
                putExtra("video_id", videoId)
                putExtra("deeplink", "clipqueue://video/$videoId?surface=$surface")
                putExtra("surface", surface)
                putExtra("cta", cta)
                putExtra("type", surface)
            }
        }
        return PendingIntent.getActivity(
            this,
            requestCode,
            open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun broadcastPi(
        requestCode: Int,
        videoId: String,
        surface: String,
        action: String,
        notifId: Int,
    ): PendingIntent {
        val intent = Intent(this, PushActionReceiver::class.java).apply {
            this.action = action
            putExtra(MainActivity.EXTRA_VIDEO_ID, videoId)
            putExtra("video_id", videoId)
            putExtra("surface", surface)
            putExtra(PushActionReceiver.EXTRA_NOTIF_ID, notifId)
        }
        return PendingIntent.getBroadcast(
            this,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun defaultHeadline(type: String): String = when (type) {
        "morning" -> getString(R.string.notif_morning_title)
        "reminder" -> getString(R.string.notif_reminder_title)
        "classified", "classify" -> getString(R.string.notif_classified_title)
        else -> getString(R.string.notif_default_title)
    }
}
