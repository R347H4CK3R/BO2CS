#include "Platform.hpp"
#import <UIKit/UIKit.h>
#include <mach/mach.h>

std::string resourceDirectory(){return [[[NSBundle mainBundle] resourcePath] UTF8String];}
std::string logDirectory(){
    NSString* documents=NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,NSUserDomainMask,YES)[0];
    NSString* logs=[documents stringByAppendingPathComponent:@"Logs"];
    [[NSFileManager defaultManager] createDirectoryAtPath:logs withIntermediateDirectories:YES attributes:nil error:nil];
    return [logs UTF8String];
}
static UIWindow* gameWindow(){
    for(UIScene* scene in [UIApplication sharedApplication].connectedScenes)
        if([scene isKindOfClass:[UIWindowScene class]])
            for(UIWindow* window in ((UIWindowScene*)scene).windows)if(window.isKeyWindow)return window;
    id<UIApplicationDelegate> delegate=[UIApplication sharedApplication].delegate;
    if([delegate respondsToSelector:@selector(window)])return delegate.window;
    return nil;
}
void safeInsets(float& l,float& r,float& t,float& b){
    UIWindow* w=gameWindow(); UIEdgeInsets i=w.safeAreaInsets;
    l=i.left;r=i.right;t=i.top;b=i.bottom;
}
void shareLogs(){
    NSString* path=[NSString stringWithUTF8String:logDirectory().c_str()];
    NSMutableArray* files=[NSMutableArray array];
    for(NSString* name in [[NSFileManager defaultManager] contentsOfDirectoryAtPath:path error:nil])
        [files addObject:[NSURL fileURLWithPath:[path stringByAppendingPathComponent:name]]];
    UIActivityViewController* activity=[[UIActivityViewController alloc] initWithActivityItems:files applicationActivities:nil];
    UIViewController* presenter=gameWindow().rootViewController;
    activity.popoverPresentationController.sourceView=presenter.view;
    activity.popoverPresentationController.sourceRect=CGRectMake(100,100,1,1);
    [presenter presentViewController:activity animated:YES completion:nil];
}
double residentMemoryMB(){
    mach_task_basic_info_data_t info;mach_msg_type_number_t count=MACH_TASK_BASIC_INFO_COUNT;
    if(task_info(mach_task_self(),MACH_TASK_BASIC_INFO,(task_info_t)&info,&count)!=KERN_SUCCESS)return 0;
    return double(info.resident_size)/(1024*1024);
}
