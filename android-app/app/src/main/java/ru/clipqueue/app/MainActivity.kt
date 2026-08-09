package ru.clipqueue.app

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.push.PushRegistrar
import ru.clipqueue.app.ui.screens.AuthScreen
import ru.clipqueue.app.ui.screens.FaqScreen
import ru.clipqueue.app.ui.screens.FolderDetailScreen
import ru.clipqueue.app.ui.screens.FoldersScreen
import ru.clipqueue.app.ui.screens.HomeScreen
import ru.clipqueue.app.ui.screens.OnboardingScreen
import ru.clipqueue.app.ui.screens.ProfileScreen
import ru.clipqueue.app.ui.screens.SaveHistoryScreen
import ru.clipqueue.app.ui.screens.VideoDetailScreen
import ru.clipqueue.app.ui.theme.ClipQueueTheme
import ru.clipqueue.app.ui.theme.CqBg

class MainActivity : ComponentActivity() {
    private val pendingAuthToken = mutableStateOf<String?>(null)
    private val pendingVideoId = mutableStateOf<String?>(null)

    private val notifPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) {
        PushRegistrar.syncIfLoggedIn(this)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        PushRegistrar.ensureChannel(this)
        ingestIntent(intent)
        maybeRequestNotifPermission()
        val app = application.clipQueue()
        if (app.session.isLoggedIn) {
            PushRegistrar.syncIfLoggedIn(this)
        }
        setContent {
            ClipQueueTheme {
                Surface(
                    modifier = Modifier
                        .fillMaxSize()
                        .safeDrawingPadding(),
                    color = CqBg,
                ) {
                    ClipQueueNav(
                        api = app.api,
                        session = app.session,
                        pendingToken = pendingAuthToken.value,
                        onTokenConsumed = { pendingAuthToken.value = null },
                        pendingVideoId = pendingVideoId.value,
                        onVideoConsumed = { pendingVideoId.value = null },
                        onLoggedIn = {
                            maybeRequestNotifPermission()
                            PushRegistrar.syncIfLoggedIn(this)
                        },
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        ingestIntent(intent)
    }

    private fun maybeRequestNotifPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (!PushRegistrar.notificationsPermissionNeeded(this)) return
        notifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
    }

    private fun ingestIntent(intent: Intent?) {
        if (intent == null) return
        // Share push / FCM tap (data payload keys become extras)
        val fromExtra = sequenceOf(
            intent.getStringExtra(EXTRA_VIDEO_ID),
            intent.getStringExtra("video_id"),
        ).mapNotNull { it?.trim()?.takeIf { s -> s.isNotBlank() } }.firstOrNull()
        if (fromExtra != null) {
            pendingVideoId.value = fromExtra
        }
        val data = intent.data ?: return
        if (data.scheme != "clipqueue") return
        when (data.host) {
            "auth" -> {
                val token = data.getQueryParameter("token")
                if (!token.isNullOrBlank()) {
                    application.clipQueue().session.token = token
                    pendingAuthToken.value = token
                }
            }
            "video" -> {
                val id = data.pathSegments.firstOrNull()?.trim().orEmpty()
                if (id.isNotBlank()) {
                    pendingVideoId.value = id
                }
            }
        }
    }

    companion object {
        const val EXTRA_VIDEO_ID = "kyro_video_id"
    }
}

@Composable
private fun ClipQueueNav(
    api: ApiClient,
    session: SessionStore,
    pendingToken: String?,
    onTokenConsumed: () -> Unit,
    pendingVideoId: String?,
    onVideoConsumed: () -> Unit,
    onLoggedIn: () -> Unit,
) {
    var loggedIn by remember { mutableStateOf(session.isLoggedIn) }
    if (pendingToken != null) {
        loggedIn = true
        onTokenConsumed()
        onLoggedIn()
    }

    if (!loggedIn) {
        AuthScreen(api, session) {
            loggedIn = true
            onLoggedIn()
        }
        return
    }

    var needOnboard by remember { mutableStateOf(!session.onboardingDone) }
    if (needOnboard) {
        OnboardingScreen(api, session) { needOnboard = false }
        return
    }

    val nav = rememberNavController()

    fun openFolder(folder: ListCard) {
        val id = folder.id ?: return
        val title = Uri.encode(folder.title.orEmpty())
        nav.navigate("folder/$id?title=$title")
    }

    fun openVideo(videoId: String) {
        if (videoId.isBlank()) return
        nav.navigate("video/${Uri.encode(videoId)}")
    }

    fun goTab(route: String) {
        nav.navigate(route) {
            popUpTo(nav.graph.findStartDestination().id) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    LaunchedEffect(pendingVideoId) {
        val id = pendingVideoId?.trim().orEmpty()
        if (id.isBlank()) return@LaunchedEffect
        openVideo(id)
        onVideoConsumed()
    }

    NavHost(navController = nav, startDestination = "home") {
        composable("home") {
            HomeScreen(
                api = api,
                onOpenVideo = ::openVideo,
                onOpenFolder = ::openFolder,
                onOpenFolders = { goTab("folders") },
                onOpenProfile = { goTab("profile") },
            )
        }
        composable("folders") {
            FoldersScreen(
                api = api,
                onBackHome = { goTab("home") },
                onOpenFolder = ::openFolder,
                onOpenProfile = { goTab("profile") },
                onOpenVideo = ::openVideo,
            )
        }
        composable(
            route = "folder/{id}?title={title}",
            arguments = listOf(
                navArgument("id") { type = NavType.IntType },
                navArgument("title") {
                    type = NavType.StringType
                    defaultValue = ""
                },
            ),
        ) { entry ->
            val id = entry.arguments?.getInt("id") ?: return@composable
            val title = Uri.decode(entry.arguments?.getString("title").orEmpty())
            FolderDetailScreen(
                api = api,
                folder = ListCard(id = id, title = title),
                onBack = { nav.popBackStack() },
                onOpenVideo = ::openVideo,
            )
        }
        composable(
            route = "video/{id}",
            arguments = listOf(navArgument("id") { type = NavType.StringType }),
            enterTransition = {
                fadeIn(tween(420)) +
                    scaleIn(initialScale = 0.96f, animationSpec = tween(480)) +
                    slideInVertically(tween(480)) { it / 14 }
            },
            exitTransition = {
                fadeOut(tween(260)) + scaleOut(targetScale = 0.99f, animationSpec = tween(260))
            },
            popEnterTransition = {
                fadeIn(tween(320)) + scaleIn(initialScale = 0.99f, animationSpec = tween(320))
            },
            popExitTransition = {
                fadeOut(tween(380)) +
                    scaleOut(targetScale = 0.96f, animationSpec = tween(400)) +
                    slideOutVertically(tween(400)) { it / 12 }
            },
        ) { entry ->
            val id = Uri.decode(entry.arguments?.getString("id").orEmpty())
            VideoDetailScreen(
                api = api,
                videoId = id,
                onBack = { nav.popBackStack() },
                onOpenVideo = ::openVideo,
            )
        }
        composable("profile") {
            ProfileScreen(
                api = api,
                session = session,
                onHome = { goTab("home") },
                onFolders = { goTab("folders") },
                onOpenHistory = { nav.navigate("saves") },
                onOpenFaq = { nav.navigate("faq") },
                onLoggedOut = { loggedIn = false },
            )
        }
        composable("faq") {
            FaqScreen(onBack = { nav.popBackStack() })
        }
        composable("saves") {
            val app = LocalContext.current.applicationContext as ClipQueueApp
            SaveHistoryScreen(
                api = api,
                localStore = app.saveHistory,
                onBack = { nav.popBackStack() },
                onOpenVideo = ::openVideo,
            )
        }
    }
}
