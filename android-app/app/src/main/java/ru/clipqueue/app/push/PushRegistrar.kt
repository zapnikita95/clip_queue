package ru.clipqueue.app.push

import android.Manifest
import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import androidx.core.content.ContextCompat
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import ru.clipqueue.app.ClipQueueApp
import ru.clipqueue.app.R
import ru.clipqueue.app.clipQueue

object PushRegistrar {
    const val CHANNEL_CLASSIFY = "kyro_classify"
    private const val TAG = "KyroPush"
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private fun appOf(context: Context): ClipQueueApp? =
        try {
            (context.applicationContext as Application).clipQueue()
        } catch (_: Exception) {
            null
        }

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val mgr = context.getSystemService(NotificationManager::class.java) ?: return
        val ch = NotificationChannel(
            CHANNEL_CLASSIFY,
            context.getString(R.string.notif_channel_classify),
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = context.getString(R.string.notif_channel_classify_desc)
        }
        mgr.createNotificationChannel(ch)
    }

    fun syncIfLoggedIn(context: Context) {
        val app = appOf(context) ?: return
        if (!app.session.isLoggedIn) return
        ensureChannel(context)
        try {
            FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
                if (!task.isSuccessful) {
                    Log.w(TAG, "FCM token failed", task.exception)
                    return@addOnCompleteListener
                }
                val token = task.result ?: return@addOnCompleteListener
                registerToken(context, token)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Firebase Messaging unavailable — replace google-services.json", e)
        }
    }

    fun onNewToken(context: Context, token: String) {
        registerToken(context, token)
    }

    private fun registerToken(context: Context, token: String) {
        val app = appOf(context) ?: return
        if (!app.session.isLoggedIn || token.isBlank()) return
        scope.launch {
            try {
                app.api.registerDevice(token)
                Log.i(TAG, "device registered")
            } catch (e: Exception) {
                Log.w(TAG, "device register failed", e)
            }
        }
    }

    fun notificationsPermissionNeeded(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return false
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.POST_NOTIFICATIONS,
        ) != PackageManager.PERMISSION_GRANTED
    }
}
