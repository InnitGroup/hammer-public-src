from app.enums.RobloxProductType import RobloxProductType
from app.enums.CurrencyType import CurrencyType

DefaultPrices = {
    RobloxProductType.Group: {
        CurrencyType.Robux: 100,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.Badge: {
        CurrencyType.Robux: 100,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.GroupRoleSet: {
        CurrencyType.Robux: 25,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.YouTubeMediaItem: {
        CurrencyType.Robux: 500,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.ImageMediaItem: {
        CurrencyType.Robux: 20,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.GamePass: {
        CurrencyType.Robux: 0,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.CashOut: {
        CurrencyType.Robux: -1,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.Audio: {
        CurrencyType.Robux: 100,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.UsernameChange: {
        CurrencyType.Robux: 1000,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.Animation: {
        CurrencyType.Robux: 0,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.Clan: {
        CurrencyType.Robux: 400,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.PrivateServer: {
        CurrencyType.Robux: -1,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.AudioShortSoundEffect: { # 0 - 10 seconds, 0 - 0.75 MB
        CurrencyType.Robux: 20,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.AudioLongSoundEffect: { # 10 - 30 seconds, 0.75 - 1.75 MB
        CurrencyType.Robux: 50,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.AudioMusic: { # 30 seconds - 2 minutes, 1.75 - 7 MB
        CurrencyType.Robux: 100,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.AudioLongMusic: { # 2 minutes - 6 minutes, 7 - 20 MB
        CurrencyType.Robux: 500,
        CurrencyType.Tickets: -1
    },
    RobloxProductType.InviteKey: {
        CurrencyType.Robux: 50,
        CurrencyType.Tickets: -1
    }
}