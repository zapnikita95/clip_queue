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

class KyroMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        super.onNewToken(token)
        PushRegistrar.onNewToken(applicationContext, token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val payload = message.data
        val videoId = payload["video_id"].orEmpty()
        val listTitle = payload["list_title"].orEmpty()
        val title = message.notification?.title
            ?: getString(R.string.app_name)
        val body = message.notification?.body
            ?: listTitle.takeIf { it.isNotBlank() }?.let { "→ $it" }
            ?: "Видео обработано"

        val open = Intent(this, MainActivity::class.java).apply {
            action = Intent.ACTION_VIEW
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            if (videoId.isNotBlank()) {
                setData(Uri.parse("clipqueue://video/$videoId?surface=push"))
                putExtra(MainActivity.EXTRA_VIDEO_ID, videoId)
                putExtra("surface", "push")
            }
        }
        val pi = PendingIntent.getActivity(
            this,
            videoId.hashCode(),
            open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val watchPi = PendingIntent.getActivity(
            this,
            videoId.hashCode() + 11,
            Intent(this, MainActivity::class.java).apply {
                action = Intent.ACTION_VIEW
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                if (videoId.isNotBlank()) {
                    setData(Uri.parse("clipqueue://video/$videoId?action=watch&surface=push"))
                    putExtra(MainActivity.EXTRA_VIDEO_ID, videoId)
                    putExtra("surface", "push")
                    putExtra("cta", "watch")
                }
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val laterPi = PendingIntent.getActivity(
            this,
            videoId.hashCode() + 12,
            Intent(this, MainActivity::class.java).apply {
                action = Intent.ACTION_VIEW
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                if (videoId.isNotBlank()) {
                    setData(Uri.parse("clipqueue://video/$videoId?action=later"))
                    putExtra(MainActivity.EXTRA_VIDEO_ID, videoId)
                    putExtra("cta", "later")
                }
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val seenPi = PendingIntent.getActivity(
            this,
            videoId.hashCode() + 13,
            Intent(this, MainActivity::class.java).apply {
                action = Intent.ACTION_VIEW
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                if (videoId.isNotBlank()) {
                    setData(Uri.parse("clipqueue://video/$videoId?action=watched"))
                    putExtra(MainActivity.EXTRA_VIDEO_ID, videoId)
                    putExtra("cta", "watched")
                }
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        PushRegistrar.ensureChannel(this)
        val notif = NotificationCompat.Builder(this, PushRegistrar.CHANNEL_CLASSIFY)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pi)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .addAction(0, "Смотреть", watchPi)
            .addAction(0, "Не сейчас", laterPi)
            .addAction(0, "Уже видел", seenPi)
            .build()
        try {
            NotificationManagerCompat.from(this).notify(
                (videoId.ifBlank { body }).hashCode(),
                notif,
            )
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS not granted
        }
    }
}
