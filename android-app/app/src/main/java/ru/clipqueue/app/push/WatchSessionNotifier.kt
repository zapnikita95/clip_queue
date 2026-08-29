package ru.clipqueue.app.push

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.RemoteInput
import ru.clipqueue.app.MainActivity
import ru.clipqueue.app.R

/**
 * Sticky-ish local notification while the user watches on YouTube.
 * Actions: mark watched · reply with progress time (RemoteInput).
 * Overlay-over-YouTube is avoided (SYSTEM_ALERT_WINDOW / Play policy).
 */
object WatchSessionNotifier {
    const val CHANNEL_WATCH = "kyro_watch"
    const val KEY_PROGRESS = "kyro_progress_text"
    const val EXTRA_TITLE = "kyro_video_title"
    const val EXTRA_DURATION = "kyro_duration_sec"

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val mgr = context.getSystemService(NotificationManager::class.java) ?: return
        val ch = NotificationChannel(
            CHANNEL_WATCH,
            context.getString(R.string.notif_channel_watch),
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = context.getString(R.string.notif_channel_watch_desc)
            setShowBadge(false)
        }
        mgr.createNotificationChannel(ch)
    }

    fun notifIdFor(videoId: String): Int = ("watch:$videoId").hashCode()

    fun show(
        context: Context,
        videoId: String,
        title: String?,
        durationSec: Int? = null,
    ) {
        if (videoId.isBlank()) return
        ensureChannel(context)
        PushRegistrar.ensureChannel(context)
        val notifId = notifIdFor(videoId)
        val displayTitle = title?.trim().orEmpty().ifBlank { "Видео на YouTube" }

        val openApp = PendingIntent.getActivity(
            context,
            notifId,
            Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra(MainActivity.EXTRA_VIDEO_ID, videoId)
                putExtra("video_id", videoId)
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val watchedPi = broadcastPi(
            context,
            notifId + 1,
            videoId,
            PushActionReceiver.ACTION_MARK_WATCHED,
            notifId,
            title = displayTitle,
            durationSec = durationSec,
            mutable = false,
        )
        val progressPi = broadcastPi(
            context,
            notifId + 2,
            videoId,
            PushActionReceiver.ACTION_MARK_PROGRESS,
            notifId,
            title = displayTitle,
            durationSec = durationSec,
            mutable = true,
        )
        val remoteInput = RemoteInput.Builder(KEY_PROGRESS)
            .setLabel(context.getString(R.string.notif_progress_hint))
            .build()
        val progressAction = NotificationCompat.Action.Builder(
            0,
            context.getString(R.string.notif_action_progress),
            progressPi,
        ).addRemoteInput(remoteInput).build()

        val builder = NotificationCompat.Builder(context, CHANNEL_WATCH)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(context.getString(R.string.notif_watch_title))
            .setContentText(displayTitle)
            .setStyle(NotificationCompat.BigTextStyle().bigText(displayTitle))
            .setContentIntent(openApp)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .addAction(0, context.getString(R.string.notif_action_watched), watchedPi)
            .addAction(progressAction)
            .setAutoCancel(false)

        try {
            NotificationManagerCompat.from(context).notify(notifId, builder.build())
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS not granted
        }
    }

    fun cancel(context: Context, videoId: String) {
        if (videoId.isBlank()) return
        runCatching {
            NotificationManagerCompat.from(context).cancel(notifIdFor(videoId))
        }
    }

    private fun broadcastPi(
        context: Context,
        requestCode: Int,
        videoId: String,
        action: String,
        notifId: Int,
        title: String?,
        durationSec: Int?,
        mutable: Boolean,
    ): PendingIntent {
        val intent = Intent(context, PushActionReceiver::class.java).apply {
            this.action = action
            putExtra(MainActivity.EXTRA_VIDEO_ID, videoId)
            putExtra("video_id", videoId)
            putExtra(PushActionReceiver.EXTRA_NOTIF_ID, notifId)
            putExtra(EXTRA_TITLE, title)
            if (durationSec != null) putExtra(EXTRA_DURATION, durationSec)
        }
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or
            if (mutable) PendingIntent.FLAG_MUTABLE else PendingIntent.FLAG_IMMUTABLE
        return PendingIntent.getBroadcast(context, requestCode, intent, flags)
    }
}
