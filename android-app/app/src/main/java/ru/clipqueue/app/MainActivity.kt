package ru.clipqueue.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import ru.clipqueue.app.data.ListCard
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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        ingestAuthIntent(intent)
        val app = application.clipQueue()
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
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        ingestAuthIntent(intent)
    }

    private fun ingestAuthIntent(intent: Intent?) {
        val data = intent?.data ?: return
        if (data.scheme == "clipqueue" && data.host == "auth") {
            val token = data.getQueryParameter("token")
            if (!token.isNullOrBlank()) {
                application.clipQueue().session.token = token
                pendingAuthToken.value = token
            }
        }
    }
}

@Composable
private fun ClipQueueNav(
    api: ApiClient,
    session: SessionStore,
    pendingToken: String?,
    onTokenConsumed: () -> Unit,
) {
    var loggedIn by remember { mutableStateOf(session.isLoggedIn) }
    if (pendingToken != null) {
        loggedIn = true
        onTokenConsumed()
    }

    if (!loggedIn) {
        AuthScreen(api, session) { loggedIn = true }
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
