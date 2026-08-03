package ru.clipqueue.app

import android.content.Context
import androidx.core.content.edit
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class SessionStore(context: Context) {
    private val appContext = context.applicationContext

    private val prefs by lazy {
        val masterKey = MasterKey.Builder(appContext)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            appContext,
            "cq_session_secure",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    /** Plain mirror so ShareReceiveActivity can read token without Compose. */
    private val mirror by lazy {
        appContext.getSharedPreferences("cq_session_mirror", Context.MODE_PRIVATE)
    }

    var token: String?
        get() = prefs.getString(KEY_TOKEN, null) ?: mirror.getString(KEY_TOKEN, null)
        set(value) {
            prefs.edit { putString(KEY_TOKEN, value) }
            mirror.edit { putString(KEY_TOKEN, value) }
        }

    var email: String?
        get() = prefs.getString(KEY_EMAIL, null)
        set(value) {
            prefs.edit { putString(KEY_EMAIL, value) }
        }

    val isLoggedIn: Boolean get() = !token.isNullOrBlank()

    fun clear() {
        prefs.edit { clear() }
        mirror.edit { clear() }
    }

    companion object {
        const val KEY_TOKEN = "token"
        const val KEY_EMAIL = "email"

        fun readMirrorToken(context: Context): String? =
            context.applicationContext
                .getSharedPreferences("cq_session_mirror", Context.MODE_PRIVATE)
                .getString(KEY_TOKEN, null)
    }
}
