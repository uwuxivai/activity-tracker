% Стилевой файл для оформления курсовой работы
% Автор: Калитвин В.А. 
% kalitvinv@yandex.ru

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{timcw}[2026/11/06 v1.0 Class for course work]
\LoadClass[14pt]{extreport}
\RequirePackage[a4paper, left=30mm, right=10mm, top=20mm, bottom=25mm]{geometry}

% Проверка движка и предупреждение
\ifx\XeTeXversion\undefined
  \ClassWarning{timcw}{%
    This class is designed for XeLaTeX (due to font handling).%
    If you get font/character errors, please compile with xelatex.%
  }
\fi

\RequirePackage{fontspec}
\RequirePackage{polyglossia}
\defaultfontfeatures{Ligatures=TeX}

%\setmainfont{Times New Roman}
%\setsansfont{Arial}
%\setmonofont{Courier New}

%\setmainfont{TeX Gyre Termes}
%\usepackage{newtxmath}

%\setmainfont{CMU Serif}
%\setsansfont{CMU Sans Serif}
%\setmonofont{CMU Typewriter Text}

%\setmainfont{PT Serif}
%\setsansfont{PT Sans}
%\setmonofont{PT Mono}

%\setmainfont{Times New Roman}[
%  Ligatures=TeX
%]

%\newfontfamily\cyrillicfont[
%    Script=Cyrillic
%]{PT Serif}

%\newfontfamily\cyrillicfontsf[
%    Script=Cyrillic
%]{PT Sans}

% Локальные шрифты проекта: компиляция не зависит от установленных
% в операционной системе PT Serif / PT Sans / PT Mono.
% Каталог fonts/ должен лежать рядом с main.tex.
\setmainfont{PTF55F.ttf}[
  Path=fonts/,
  BoldFont=PTF75F.ttf,
  ItalicFont=PTF56F.ttf,
  BoldItalicFont=PTF76F.ttf
]
\setsansfont{PTS55F.ttf}[
  Path=fonts/,
  BoldFont=PTS75F.ttf,
  ItalicFont=PTS56F.ttf,
  BoldItalicFont=PTS76F.ttf
]
\setmonofont{PTM55F.ttf}[
  Path=fonts/,
  BoldFont=PTM75F.ttf
]

% Те же локальные файлы используются для кириллицы.
\newfontfamily\cyrillicfont{PTF55F.ttf}[
  Path=fonts/,
  Script=Cyrillic,
  BoldFont=PTF75F.ttf,
  ItalicFont=PTF56F.ttf,
  BoldItalicFont=PTF76F.ttf
]
\newfontfamily\cyrillicfontsf{PTS55F.ttf}[
  Path=fonts/,
  Script=Cyrillic,
  BoldFont=PTS75F.ttf,
  ItalicFont=PTS56F.ttf,
  BoldItalicFont=PTS76F.ttf
]
\newfontfamily\cyrillicfonttt{PTM55F.ttf}[
  Path=fonts/,
  Script=Cyrillic,
  BoldFont=PTM75F.ttf
]

\setdefaultlanguage{russian}
%\usepackage{timcw}

\RequirePackage{misccorr}    % точка в заголовках, но не в ссылках
\RequirePackage{indentfirst} % абзацный отступ после заголовков
\RequirePackage{graphicx}
\RequirePackage{setspace}
\onehalfspacing % полуторный интервал во всём документе

\RequirePackage{titlesec}


\renewcommand{\chaptername}{Глава} % имя для текста и содержания
% Заголовок главы: 14pt, межстрочный 16pt, жирный
\titleformat{\chapter}
  {\fontsize{16pt}{16pt}\bfseries\centering} % оформление шрифта
  {\chaptername\ \thechapter.}                    % как выводить номер
  {1em}                            % отступ между номером и текстом
  {}                               % дополнительный код перед заголовком

% Глава в содержании: 14pt, межстрочный 16pt, жирный
%\renewcommand{\thechapter}{\arabic{chapter}}
%\renewcommand{\chaptermark}[1]{\markboth{Глава \thechapter. #1}{}}

\RequirePackage{tocloft}

% --- Название оглавления ---
% Выполнить после начальной настройки языка.
\AddToHook{begindocument/end}{%
  \renewcommand{\contentsname}{Содержание}%
}

% --- Заголовок оглавления по центру ---
\renewcommand{\cfttoctitlefont}{%
  \hfill\normalfont\Large\bfseries
}
\renewcommand{\cftaftertoctitle}{%
  \hfill\mbox{}%
}

% "Глава 1." перед названием в оглавлении
\renewcommand{\cftchappresnum}{Глава~} % префикс
%\renewcommand{\cftchapaftersnum}{.\ }  % точка после номера

% Подобрать ширину поля под "Глава 10."
\newlength{\tocchaplen}
\settowidth{\tocchaplen}{Глава~100.\ \ } % примерный максимум
\setlength{\cftchapnumwidth}{\tocchaplen}

% --- Заголовки section по центру ---
\makeatletter
\renewcommand\section{%
  \@startsection{section}{1}{\z@}%
    {-3.5ex \@plus -1ex \@minus -.2ex}%
    {2.3ex \@plus .2ex}%
    {\centering\bfseries}%
}
\makeatother

% --- Точки в списке литературы ---
\makeatletter
\renewcommand\@biblabel[1]{#1.}
\makeatother

\makeatletter

% --- Поля титульного листа ---
\newcommand{\cw@topic}{}
\newcommand{\cw@course}{}
\newcommand{\cw@group}{}
\newcommand{\cw@student}{}
\newcommand{\cw@cityyear}{}
\newcommand{\cw@direction}{}
\newcommand{\cw@profile}{}

% --- Команды настройки ---
\newcommand{\cwtopic}[1]{%
  \renewcommand{\cw@topic}{#1}%
}

\newcommand{\cwcourse}[1]{%
  \renewcommand{\cw@course}{#1}%
}

\newcommand{\cwgroup}[1]{%
  \renewcommand{\cw@group}{#1}%
}

\newcommand{\cwstudent}[1]{%
  \renewcommand{\cw@student}{#1}%
}

\newcommand{\cwcityyear}[1]{%
  \renewcommand{\cw@cityyear}{#1}%
}

\newcommand{\cwdirection}[1]{%
  \renewcommand{\cw@direction}{#1}%
}

\newcommand{\cwprofile}[1]{%
  \renewcommand{\cw@profile}{#1}%
}

% --- Проверка темы ---
\AtBeginDocument{%
  \ifx\cw@topic\@empty
    \ClassError{timcw}{Тема курсового проекта не задана}{%
      Укажите тему в преамбуле командой
      \string\cwtopic{Тема курсового проекта}.%
    }%
  \fi
}

% --- Команда титульного листа ---
\newcommand{\cwtitle}{%
  \clearpage
  \begin{singlespacing}
  \thispagestyle{empty}

  % Шапка
  \noindent
  \begin{minipage}[c]{0.12\textwidth}
    \includegraphics[width=0.96\linewidth]{tim-logo.png}%
  \end{minipage}%
  \hfill
  \begin{minipage}[c]{0.88\textwidth}
    \scriptsize
    \centering

    \textbf{МИНИСТЕРСТВО СЕЛЬСКОГО ХОЗЯЙСТВА
    РОССИЙСКОЙ ФЕДЕРАЦИИ}\\[0.2cm]

    ФЕДЕРАЛЬНОЕ ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ
    ОБРАЗОВАТЕЛЬНОЕ УЧРЕЖДЕНИЕ
    ВЫСШЕГО ОБРАЗОВАНИЯ\\[0.2cm]

    \textbf{«РОССИЙСКИЙ ГОСУДАРСТВЕННЫЙ
    АГРАРНЫЙ УНИВЕРСИТЕТ --
    МСХА имени К.\,А.~ТИМИРЯЗЕВА»}\\[0.2cm]

    \textbf{(ФГБОУ ВО РГАУ --
    МСХА имени К.\,А.~Тимирязева)}
    \par
  \end{minipage}

  \par
  \bigskip

  \noindent\rule{\textwidth}{0.4pt}\\[-2.0ex]
  \rule{\textwidth}{0.4pt}
  \par

  % Подразделение и образовательная программа
  {\small
    \begin{center}
      Институт экономики и управления\\[0.1cm]
      Кафедра статистики и кибернетики\\[0.5cm]

      Направление: \cw@direction\\
      Направленность: \cw@profile\\[0.8cm]
    \end{center}
  }

  % Вид работы
  {\Large
    \begin{center}
      \textbf{КУРСОВОЙ ПРОЕКТ}
    \end{center}
  }

  % Тема
  \noindent
  на тему: «\cw@topic».\par
  \vspace{1.0cm}

  % Сведения о студенте и защите
  {\small
    \noindent
    \hfill
    \begin{minipage}[t]{0.55\textwidth}
      Выполнил:\\
      Студент \cw@course \ курса группы \cw@group\\[1ex]
      \cw@student\\[1ex]

      Дата регистрации КП\\[1ex]
      на кафедре: \rule{4cm}{0.4pt}\\[0.2cm]

      Допущен к защите\\[0.2cm]
      Руководитель:\\[0.3cm]

      \rule{\linewidth}{0.4pt}\\
      {\footnotesize
        учёная степень, учёное звание, ФИО
      }\\[0.5cm]

      Члены комиссии:\\[0.2cm]
      \rule{0.73\linewidth}{0.4pt}\hfill
      \rule{0.23\linewidth}{0.4pt}\\[-2pt]
      {\footnotesize
        учёная степень, учёное звание, ФИО
        \hfill подпись
      }\\[0.2cm]
      \rule{0.73\linewidth}{0.4pt}\hfill
      \rule{0.23\linewidth}{0.4pt}\\[-2pt]
      {\footnotesize
        учёная степень, учёное звание, ФИО
        \hfill подпись
      }\\[0.2cm]
      \rule{0.73\linewidth}{0.4pt}\hfill
      \rule{0.23\linewidth}{0.4pt}\\[-2pt]
      {\footnotesize
        учёная степень, учёное звание, ФИО
        \hfill подпись
      }\\[0.5cm]

      Оценка \hrulefill\\[0.4cm]
      Дата защиты \hrulefill
    \end{minipage}
    \par
  }

  \vspace{1.0cm}

  \begin{center}
    \cw@cityyear
  \end{center}

  \clearpage
  \end{singlespacing}
}

\makeatother




% --- Оформление списка литературы по центру ---
\newcommand{\centeredrefname}{%
  \renewcommand\bibname{\centering Список использованных источников}%
}

% --- Удобные команды для Введения, Заключения, Приложений ---
\newcommand{\intro}{%
  \addcontentsline{toc}{chapter}{Введение}%
  \chapter*{Введение}%
}

\newcommand{\conclusion}{%
  \addcontentsline{toc}{chapter}{Заключение}%
  \chapter*{Заключение}%
}

\newcommand{\applications}{%
  \addcontentsline{toc}{chapter}{Приложения}%
  \chapter*{Приложения}%
}