#pragma once
#include <string>
std::string resourceDirectory();
std::string logDirectory();
void safeInsets(float& left,float& right,float& top,float& bottom);
void shareLogs();
double residentMemoryMB();
